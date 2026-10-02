from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from ..domain import Point, Rotation, ScaleCandidate, ScaleCell, ScaleRatio, TemplateProfile
from ..errors import AppError
from .document import TraversalBudget
from ..templates.plot_window_transform import rotate
from ..templates.scale_label import parse_internal_scale
from ..templates.structural_signature import StructuralSignature, score_signature


@dataclass(frozen=True)
class DetectionLimits:
    max_nested_blocks: int
    max_nested_entities: int

    def __post_init__(self) -> None:
        if self.max_nested_blocks <= 0 or self.max_nested_entities <= 0:
            raise ValueError("detection limits must be positive")


def _validated_point(snapshot: dict[str, object]) -> tuple[float, float]:
    try:
        raw = snapshot["point"]
        x, y = float(raw[0]), float(raw[1])
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise AppError("E303", "invalid scale detection geometry") from exc
    if not (math.isfinite(x) and math.isfinite(y)):
        raise AppError("E303", "non-finite scale detection geometry")
    return x, y


def _bounded_text_and_insert_snapshots(document: Any, limits: DetectionLimits) -> list[dict[str, object]]:
    detection_view = getattr(document, "for_scale_detection", None)
    if detection_view is not None:
        document = detection_view()
    initial = list(document.filtered_snapshots(("TEXT", "MTEXT", "INSERT"), bounds=None))
    top_level_ratios: list[dict[str, object]] = []
    for item in initial:
        if item.get("type") == "INSERT":
            continue
        try:
            parse_internal_scale(str(item.get("text", "")))
        except AppError:
            continue
        top_level_ratios.append(item)
    top_level_scale_labels = [
        item for item in initial
        if item.get("type") != "INSERT"
        and str(item.get("text", "")).strip().casefold() == "scale"
    ]
    references = [item for item in initial if item.get("type") == "INSERT"]
    known_skip = getattr(document, "is_known_noncontributing_text_insert", None)
    if known_skip is not None:
        references = [reference for reference in references if not bool(known_skip(reference))]
    snapshots = list(initial)
    budget = TraversalBudget(
        max_roots=limits.max_nested_blocks,
        max_blocks=limits.max_nested_blocks,
        max_entities=limits.max_nested_entities,
    )
    classification_budget = TraversalBudget(
        max_roots=limits.max_nested_entities,
        max_blocks=limits.max_nested_entities,
        max_entities=limits.max_nested_entities,
    )
    contributing: list[dict[str, object]] = []
    relevance_by_definition: dict[str, bool] = {}
    skip_text = getattr(document, "is_noncontributing_text_insert", None)
    legacy_skip = getattr(document, "is_noncontributing_unsupported_insert", None)
    for reference in references:
        block_name = str(reference.get("block_name", ""))
        unsupported = bool(legacy_skip(reference, budget=budget)) if legacy_skip is not None else False
        needs_classification = skip_text is not None and (
            legacy_skip is None or unsupported or len(references) > limits.max_nested_blocks
        )
        if needs_classification:
            noncontributing = relevance_by_definition.get(block_name)
            if noncontributing is None:
                noncontributing = bool(skip_text(reference, budget=classification_budget))
                relevance_by_definition[block_name] = noncontributing
            if noncontributing:
                continue
        elif skip_text is None and unsupported:
            continue
        budget.visit_root()
        contributing.append(reference)
    prioritized_ratio_point: tuple[float, float] | None = None
    if len(top_level_ratios) == 1 and len(top_level_scale_labels) <= 1:
        prioritized_ratio_point = _validated_point(top_level_ratios[0])
        contributing.sort(
            key=lambda reference: (
                (_validated_point(reference)[0] - prioritized_ratio_point[0]) ** 2
                + (_validated_point(reference)[1] - prioritized_ratio_point[1]) ** 2
            )
        )
    if prioritized_ratio_point is not None and len(top_level_scale_labels) == 1:
        contributing = []

    for reference in contributing:
        nested = document.nested_text_snapshots(
            reference,
            budget=budget,
        )
        snapshots.extend(nested)
        if prioritized_ratio_point is not None and sum(
            str(item.get("text", "")).strip().casefold() == "scale"
            for item in nested
        ) == 1:
            # The approved input contract guarantees one Scale cell per DWG.
            # Once the block nearest the unique top-level ratio supplies it,
            # scanning unrelated model-content definitions adds only COM cost.
            break
    for item in snapshots:
        _validated_point(item)
    return snapshots


def _object_key(snapshot: dict[str, object], index: int) -> tuple[str, object]:
    handle = str(snapshot.get("handle", "")).strip()
    path = tuple(snapshot.get("instance_path", ()))
    return ("physical", (path, handle)) if handle else ("object", index)


def detect_scale_cell(
    document: Any,
    limits: DetectionLimits,
    profiles: tuple[TemplateProfile, ...],
    fallback_matcher=None,
) -> ScaleCell:
    """Read exactly one Scale cell at learned, quarter-turn value geometry."""

    snapshots = _bounded_text_and_insert_snapshots(document, limits)
    label_by_key: dict[tuple[str, object], dict[str, object]] = {}
    for index, item in enumerate(snapshots):
        if str(item.get("text", "")).strip().casefold() == "scale":
            label_by_key[_object_key(item, index)] = item
    labels = tuple(label_by_key.values())
    if len(labels) != 1:
        raise AppError("E303", f"expected exactly one Scale label, found {len(labels)}")
    if not profiles:
        raise AppError("E308", "learned Scale-value geometry is unavailable")

    label = labels[0]
    lx, ly = _validated_point(label)
    expected: list[tuple[ScaleRatio, float, float, float, Rotation]] = []
    for profile in profiles:
        offset = profile.scale_value_offset
        tolerance = profile.scale_value_tolerance
        if (
            not (math.isfinite(offset.x) and math.isfinite(offset.y))
            or isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or tolerance <= 0
        ):
            raise AppError("E308", "invalid learned Scale-value geometry")
        for rotation in (0, 90, 180, 270):
            rotated = rotate(offset, rotation)
            expected.append((profile.scale, lx + rotated.x, ly + rotated.y, float(tolerance), rotation))

    label_keys = set(label_by_key)
    value_by_key: dict[tuple[str, object], dict[str, object]] = {}
    valid_by_key: dict[
        tuple[str, object],
        tuple[dict[str, object], tuple[tuple[ScaleRatio, float, float, float, Rotation], ...]],
    ] = {}
    for index, item in enumerate(snapshots):
        key = _object_key(item, index)
        if key in label_keys or item.get("type") not in {"TEXT", "MTEXT", "ATTRIB"} or "text" not in item:
            continue
        x, y = _validated_point(item)
        matches = tuple(
            target for target in expected
            if (x - target[1]) ** 2 + (y - target[2]) ** 2 <= target[3] ** 2
        )
        if matches:
            value_by_key[key] = item
        try:
            token_scale = parse_internal_scale(str(item.get("text", "")))
        except AppError:
            continue
        scale_targets = tuple(target for target in expected if target[0] == token_scale)
        applicable = scale_targets or tuple(expected)
        token_matches = tuple(
            target for target in applicable
            if (x - target[1]) ** 2 + (y - target[2]) ** 2 <= target[3] ** 2
        )
        if token_matches:
            valid_by_key[key] = (item, token_matches)

    fallback_rotation = None
    if not valid_by_key and fallback_matcher is not None:
        # Unknown scale must not merge the value regions of all 13 templates.
        # Establish one frame from linework, then inspect only its own value cell.
        provisional = ScaleCell(Point(lx, ly), "blank", None, str(label.get("handle", "")))
        decision = fallback_matcher(provisional)
        chosen = next((p for p in profiles if p.profile_id == decision.candidate.profile_id), None)
        fallback_rotation = decision.candidate.rotation
        if chosen is None or fallback_rotation not in (0, 90, 180, 270):
            raise AppError("E303", "structural fallback returned an invalid frame")
        offset = rotate(chosen.scale_value_offset, fallback_rotation)
        targets = ((chosen.scale, lx + offset.x, ly + offset.y,
                    float(chosen.scale_value_tolerance), fallback_rotation),)
        value_by_key = {
            key: item for key, item in value_by_key.items()
            if any((_validated_point(item)[0] - t[1]) ** 2
                   + (_validated_point(item)[1] - t[2]) ** 2 <= t[3] ** 2 for t in targets)
        }

    if valid_by_key:
        if len(valid_by_key) > 1:
            raise AppError("E304", "multiple Scale value-cell objects matched")
        value, chosen_targets = next(iter(valid_by_key.values()))
        collocated = {
            key: item for key, item in value_by_key.items()
            if any(
                (_validated_point(item)[0] - target[1]) ** 2
                + (_validated_point(item)[1] - target[2]) ** 2
                <= target[3] ** 2
                for target in chosen_targets
            )
        }
        if len(collocated) > 1:
            raise AppError("E304", "multiple Scale value-cell objects matched")
    else:
        if len(value_by_key) > 1:
            raise AppError("E304", "multiple Scale value-cell objects matched")
        value = next(iter(value_by_key.values()), None)

    raw = str(value.get("text", "")).strip() if value is not None else ""
    cell_anchor = Point(lx, ly)
    handle = str(label.get("handle", ""))
    if not raw:
        return ScaleCell(cell_anchor, "blank", None, handle, fallback_rotation)
    if raw.casefold() == "n/a":
        return ScaleCell(cell_anchor, "na", None, handle, fallback_rotation)
    try:
        parse_internal_scale(raw)
    except AppError as exc:
        raise AppError("E305", f"unsupported Scale value: {raw}") from exc
    if not valid_by_key:
        raise AppError("E305", "Scale ratio does not match its learned value-cell geometry")
    rotations = {target[4] for target in chosen_targets}
    rotation_hint = next(iter(rotations)) if len(rotations) == 1 else None
    return ScaleCell(cell_anchor, "valid", raw, handle, rotation_hint)


def detect_scale_candidates(document: Any, limits: DetectionLimits) -> list[ScaleCandidate]:
    """Find each Scale label and its nearest valid ratio in bounded snapshots."""

    snapshots = _bounded_text_and_insert_snapshots(document, limits)
    labels = [item for item in snapshots if str(item.get("text", "")).strip().casefold() == "scale"]
    values: list[dict[str, object]] = []
    for item in snapshots:
        try:
            parse_internal_scale(str(item.get("text", "")))
        except AppError:
            continue
        values.append(item)

    candidates: list[ScaleCandidate] = []
    for label in labels:
        lx, ly = _validated_point(label)
        nearby = sorted(
            values,
            key=lambda item: (
                (_validated_point(item)[0] - lx) ** 2 + (_validated_point(item)[1] - ly) ** 2,
                str(item.get("handle", "")),
            ),
        )
        if nearby:
            value = nearby[0]
            candidates.append(
                ScaleCandidate(
                    anchor=Point(lx, ly),
                    token=str(value["text"]),
                    handle=str(label.get("handle", "")),
                )
            )
    return candidates


def verify_rotation(document: Any, profile: TemplateProfile, candidate: Any) -> float:
    """Score registered linework using only a bounded server-side geometry query."""

    signature = profile.structural_signature
    if not isinstance(signature, StructuralSignature):
        raise AppError("E308", "profile structural signature is unavailable")
    snapshots = document.filtered_geometry_snapshots(candidate.frame)
    observed = []
    for item in snapshots:
        try:
            start = Point(float(item["start"][0]), float(item["start"][1]))
            end = Point(float(item["end"][0]), float(item["end"][1]))
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
            raise AppError("E303", "invalid bounded structural geometry") from exc
        observed.append((start, end))
    try:
        return score_signature(
            signature,
            observed,
            candidate.scale_candidate.anchor,
            profile.scale_anchor,
            candidate.rotation,
            profile.position_tolerance,
        )
    except ValueError as exc:
        raise AppError("E303", "invalid structural candidate geometry") from exc
