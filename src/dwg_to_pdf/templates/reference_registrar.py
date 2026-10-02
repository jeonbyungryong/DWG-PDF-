from __future__ import annotations

import math
from pathlib import Path

from ..errors import AppError
from ..domain import Point, Rect
from ..gstarcad.document import TraversalBudget
from .scale_label import parse_internal_scale, parse_reference_filename
from .structural_signature import signature_from_raw, signature_to_raw


def _point(raw: object, description: str) -> list[float]:
    try:
        point = [float(raw[0]), float(raw[1])]
    except (TypeError, ValueError, IndexError, OverflowError) as exc:
        raise AppError("E306", f"invalid {description}") from exc
    if not all(math.isfinite(value) for value in point):
        raise AppError("E306", f"non-finite {description}")
    return point


def _rect(raw: object, description: str) -> list[list[float]]:
    lower, upper = _point(raw[0], description), _point(raw[1], description)
    if lower[0] >= upper[0] or lower[1] >= upper[1]:
        raise AppError("E306", f"inverted {description}")
    return [lower, upper]


def _bbox(snapshot: dict[str, object], description: str) -> list[list[float]]:
    try:
        return _rect(snapshot["bbox"], description)
    except KeyError as exc:
        raise AppError("E306", f"missing measured {description}") from exc


def _distinct_descending(values: list[float], tolerance: float) -> list[float]:
    ordered: list[float] = []
    for value in sorted(values, reverse=True):
        if not ordered or not math.isclose(value, ordered[-1], abs_tol=tolerance, rel_tol=0.0):
            ordered.append(value)
    return ordered


def _learn_scale_value_cell(
    label_point: list[float],
    segments: list[tuple[list[float], list[float], str]],
    tolerance: float,
    source: Path,
) -> list[list[float]]:
    """Measure the table cell immediately below the unique Scale label."""

    label_x, label_y = label_point
    horizontal_levels = []
    for start, end, _ in segments:
        if (
            math.isclose(start[1], end[1], abs_tol=tolerance, rel_tol=0.0)
            and min(start[0], end[0]) - tolerance <= label_x <= max(start[0], end[0]) + tolerance
            and start[1] < label_y - tolerance
        ):
            horizontal_levels.append((start[1] + end[1]) / 2.0)
    levels = _distinct_descending(horizontal_levels, tolerance)
    if len(levels) < 2:
        raise AppError("E306", "Scale-value cell horizontal grid boundaries were not found", source)
    top, bottom = levels[0], levels[1]
    middle_y = (top + bottom) / 2.0

    left_candidates: list[float] = []
    right_candidates: list[float] = []
    for start, end, _ in segments:
        if not math.isclose(start[0], end[0], abs_tol=tolerance, rel_tol=0.0):
            continue
        if not (min(start[1], end[1]) - tolerance <= middle_y <= max(start[1], end[1]) + tolerance):
            continue
        x = (start[0] + end[0]) / 2.0
        if x < label_x - tolerance:
            left_candidates.append(x)
        elif x > label_x + tolerance:
            right_candidates.append(x)
    if not left_candidates or not right_candidates:
        raise AppError("E306", "Scale-value cell vertical grid boundaries were not found", source)
    left, right = max(left_candidates), min(right_candidates)
    return _rect(((left, bottom), (right, top)), "Scale-value table cell")


def _point_in_rect(point: list[float], bounds: list[list[float]], tolerance: float) -> bool:
    return (
        bounds[0][0] - tolerance <= point[0] <= bounds[1][0] + tolerance
        and bounds[0][1] - tolerance <= point[1] <= bounds[1][1] + tolerance
    )


def extract_reference_snapshot(
    document: object,
    source: Path,
    *,
    max_nested_blocks: int,
    max_nested_entities: int,
) -> dict[str, object]:
    """Extract one approved reference using filtered and bounded COM queries."""

    ratio = parse_reference_filename(source)
    snapshots = list(document.filtered_snapshots(("TEXT", "MTEXT", "INSERT"), bounds=None))
    roots = [item for item in snapshots if item.get("type") == "INSERT"]
    budget = TraversalBudget(max_nested_blocks, max_nested_blocks, max_nested_entities)
    for _ in roots:
        budget.visit_root()
    for reference in roots:
        snapshots.extend(document.nested_text_snapshots(reference, budget=budget))

    labels = [item for item in snapshots if str(item.get("text", "")).strip().casefold() == "scale"]
    if len(labels) != 1:
        raise AppError("E303", f"reference must contain exactly one Scale label, found {len(labels)}", source)
    label_point = _point(labels[0].get("point"), "Scale label point")
    label_bbox = _bbox(labels[0], "Scale label bbox")
    label_width = label_bbox[1][0] - label_bbox[0][0]
    label_height = label_bbox[1][1] - label_bbox[0][1]
    measurement_tolerance = min(label_width, label_height) / 1000.0
    if not math.isfinite(measurement_tolerance) or measurement_tolerance <= 0:
        raise AppError("E306", "Scale label bbox cannot derive a positive measurement tolerance", source)

    window = _rect(document.approved_reference_window(), "approved reference Window")
    expected_width, expected_height = (float(value) for value in ratio.a3_model_size())
    if not (
        math.isclose(window[1][0] - window[0][0], expected_width, abs_tol=measurement_tolerance, rel_tol=0)
        and math.isclose(window[1][1] - window[0][1], expected_height, abs_tol=measurement_tolerance, rel_tol=0)
    ):
        raise AppError("E301", "approved reference Window does not match A3 model dimensions", source)
    bounds = Rect(Point(*window[0]), Point(*window[1]))
    geometry = document.filtered_geometry_snapshots(bounds)
    segments: list[tuple[list[float], list[float], str]] = []
    label_path = tuple(labels[0].get("instance_path", ()))
    grid_path = label_path[:-1] if label_path else ()
    cell_segments: list[tuple[list[float], list[float], str]] = []
    for item in geometry:
        start = _point(item.get("start"), "structural segment start")
        end = _point(item.get("end"), "structural segment end")
        if start != end:
            segment = (start, end, str(item.get("handle", "")))
            segments.append(segment)
            if tuple(item.get("instance_path", ())) == grid_path:
                cell_segments.append(segment)

    if not cell_segments:
        raise AppError("E306", "Scale-value table grid block geometry was not found", source)
    value_cell = _learn_scale_value_cell(label_point, cell_segments, measurement_tolerance, source)
    values_by_key: dict[tuple[object, ...], dict[str, object]] = {}
    for index, item in enumerate(snapshots):
        if item is labels[0] or item.get("type") == "INSERT":
            continue
        try:
            parse_internal_scale(str(item.get("text", "")))
        except AppError:
            continue
        point = _point(item.get("point"), "Scale value point")
        _bbox(item, "Scale value bbox")
        if not _point_in_rect(point, value_cell, measurement_tolerance):
            continue
        handle = str(item.get("handle", "")).strip()
        instance_path = tuple(item.get("instance_path", ()))
        key: tuple[object, ...] = ("physical", instance_path, handle) if handle else ("object", index)
        values_by_key[key] = item
    values = tuple(values_by_key.values())
    if not values:
        raise AppError("E303", "reference Scale-value table cell contains no valid ratio", source)
    if len(values) != 1:
        raise AppError("E304", "reference Scale-value table cell contains multiple valid ratios", source)
    value_item = values[0]
    value_point = _point(value_item.get("point"), "Scale value point")
    value_bbox = _bbox(value_item, "Scale value bbox")
    scale_value_tolerance = min(
        value_bbox[1][0] - value_bbox[0][0],
        value_bbox[1][1] - value_bbox[0][1],
    ) / 2.0
    if not math.isfinite(scale_value_tolerance) or scale_value_tolerance <= 0:
        raise AppError("E306", "Scale value bbox cannot derive a positive tolerance", source)

    left, bottom = window[0]
    right, top = window[1]
    sides: list[tuple[list[float], list[float], str]] = []
    for axis, boundary in ((0, left), (0, right), (1, bottom), (1, top)):
        matching = [
            segment for segment in segments
            if abs(segment[0][axis] - boundary) <= measurement_tolerance
            and abs(segment[1][axis] - boundary) <= measurement_tolerance
        ]
        if not matching:
            raise AppError("E306", "reference frame edge is missing from bounded geometry", source)
        sides.append(max(matching, key=lambda item: (math.dist(item[0], item[1]), item[2])))

    def is_frame_boundary(item: tuple[list[float], list[float], str]) -> bool:
        return any(
            abs(item[0][axis] - boundary) <= measurement_tolerance
            and abs(item[1][axis] - boundary) <= measurement_tolerance
            for axis, boundary in ((0, left), (0, right), (1, bottom), (1, top))
        )

    title = [
        item for item in segments
        if not is_frame_boundary(item)
        and min(item[0][0], item[1][0]) >= left + expected_width * 0.55
        and max(item[0][1], item[1][1]) <= bottom + expected_height * 0.40
    ]
    title.sort(key=lambda item: (-math.dist(item[0], item[1]), item[2], item[0], item[1]))
    title = title[:32]
    if not title:
        raise AppError("E306", "reference title-block geometry was not found", source)
    selected = sides + title
    position_tolerance = min(math.dist(start, end) for start, end, _ in selected) / 1000.0
    if not math.isfinite(position_tolerance) or position_tolerance <= 0:
        raise AppError("E306", "structural geometry cannot derive a positive tolerance", source)
    relative = [
        [[start[0] - label_point[0], start[1] - label_point[1]],
         [end[0] - label_point[0], end[1] - label_point[1]]]
        for start, end, _ in selected
    ]
    orientation = max(
        (point for segment in relative[4:] for point in segment),
        key=lambda point: (point[0] ** 2 + point[1] ** 2, point[0], point[1]),
    )
    return {
        "frame": window,
        "scale_label_point": label_point,
        "scale_value_point": value_point,
        "scale_value": str(value_item.get("text", "")),
        "scale_value_cell": value_cell,
        "reference_window": window,
        "position_tolerance": position_tolerance,
        "scale_value_tolerance": scale_value_tolerance,
        "structural_signature": {
            "segments": relative,
            "frame_segment_count": 4,
            "title_segment_count": len(title),
            "orientation_anchor": orientation,
        },
    }


def register_reference(
    snapshot: dict[str, object], source: Path, sha256: str, *, source_root: Path
) -> dict[str, object]:
    filename_scale = parse_reference_filename(source)
    try:
        internal_scale = parse_internal_scale(str(snapshot["scale_value"]))
    except (KeyError, AppError) as exc:
        raise AppError("E303", "reference must contain one valid Scale value", source) from exc
    if filename_scale != internal_scale:
        raise AppError("E305", "reference filename and internal Scale disagree", source)
    if len(sha256) != 64 or any(character not in "0123456789abcdefABCDEF" for character in sha256):
        raise AppError("E308", "invalid reference SHA-256", source)

    frame = _rect(snapshot["frame"], "reference frame")
    window = _rect(snapshot["reference_window"], "approved reference Window")
    expected_width, expected_height = (float(value) for value in filename_scale.a3_model_size())
    try:
        tolerance = float(snapshot["position_tolerance"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise AppError("E308", "missing learned structural tolerance", source) from exc
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise AppError("E308", "learned structural tolerance must be finite and positive", source)
    if not (
        math.isclose(window[1][0] - window[0][0], expected_width, abs_tol=tolerance, rel_tol=0.0)
        and math.isclose(window[1][1] - window[0][1], expected_height, abs_tol=tolerance, rel_tol=0.0)
    ):
        raise AppError("E301", "approved reference Window does not match A3 model dimensions", source)
    if not (
        math.isclose(frame[1][0] - frame[0][0], expected_width, abs_tol=tolerance, rel_tol=0.0)
        and math.isclose(frame[1][1] - frame[0][1], expected_height, abs_tol=tolerance, rel_tol=0.0)
    ):
        raise AppError("E301", "reference frame does not match A3 model dimensions", source)

    label = _point(snapshot["scale_label_point"], "Scale label point")
    value = _point(snapshot["scale_value_point"], "Scale value point")
    try:
        signature = signature_from_raw(snapshot["structural_signature"])
        position_tolerance = float(snapshot["position_tolerance"])
        value_tolerance = float(snapshot["scale_value_tolerance"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise AppError("E308", "invalid learned reference geometry", source) from exc
    if not all(math.isfinite(number) and number > 0 for number in (position_tolerance, value_tolerance)):
        raise AppError("E308", "learned tolerances must be finite and positive", source)

    try:
        portable_source = source.resolve(strict=True).relative_to(source_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise AppError("E308", "reference source must be under the explicit source root", source) from exc
    if portable_source.is_absolute() or ".." in portable_source.parts:
        raise AppError("E308", "reference source path must be portable", source)

    return {
        "profile_id": f"a3-{internal_scale.numerator}-to-{internal_scale.denominator}-v1",
        "scale": {"numerator": str(internal_scale.numerator), "denominator": str(internal_scale.denominator)},
        "source": {"path": portable_source.as_posix(), "sha256": sha256.upper()},
        "approved": True,
        "frame": frame,
        "scale_anchor": label,
        "scale_value_offset": [value[0] - label[0], value[1] - label[1]],
        "scale_value_tolerance": value_tolerance,
        "orientation_anchor": [
            label[0] + signature.orientation_anchor.x,
            label[1] + signature.orientation_anchor.y,
        ],
        "reference_window": window,
        "position_tolerance": position_tolerance,
        "structural_signature": signature_to_raw(signature),
    }
