import math

from ..domain import FrameCandidate, Point, Rect, Rotation, ScaleCandidate, TemplateProfile
from ..errors import AppError

_ROTATIONS: tuple[Rotation, ...] = (0, 90, 180, 270)
_INVERSE_ROTATION: dict[Rotation, Rotation] = {0: 0, 90: 270, 180: 180, 270: 90}


def _approved_rotation(rotation: object) -> Rotation:
    if isinstance(rotation, bool) or rotation not in _ROTATIONS:
        raise AppError("E307", "rotation must be one of 0, 90, 180, or 270 degrees")
    return rotation  # type: ignore[return-value]


def rotate(point: Point, rotation: Rotation) -> Point:
    """Rotate a point rigidly around the model origin by an approved quarter-turn."""

    rotation = _approved_rotation(rotation)
    if rotation == 0:
        return point
    if rotation == 90:
        return Point(-point.y, point.x)
    if rotation == 180:
        return Point(-point.x, -point.y)
    return Point(point.y, -point.x)


def inverse_plot_rotation(frame_rotation: Rotation) -> Rotation:
    return _INVERSE_ROTATION[_approved_rotation(frame_rotation)]


def _finite(point: Point) -> bool:
    return math.isfinite(point.x) and math.isfinite(point.y)


def _transform(
    point: Point,
    source_anchor: Point,
    target_anchor: Point,
    rotation: Rotation,
) -> Point:
    rotated_anchor = rotate(source_anchor, rotation)
    moved = rotate(point, rotation)
    return Point(
        moved.x + target_anchor.x - rotated_anchor.x,
        moved.y + target_anchor.y - rotated_anchor.y,
    )


def _corners(rect: Rect) -> tuple[Point, ...]:
    return (
        rect.lower_left,
        Point(rect.upper_right.x, rect.lower_left.y),
        rect.upper_right,
        Point(rect.lower_left.x, rect.upper_right.y),
    )


def _bounds(points: tuple[Point, ...], code: str, label: str) -> Rect:
    if not points or any(not _finite(point) for point in points):
        raise AppError(code, f"computed {label} contains non-finite coordinates")
    lower_left = Point(min(point.x for point in points), min(point.y for point in points))
    upper_right = Point(max(point.x for point in points), max(point.y for point in points))
    try:
        return Rect(lower_left, upper_right)
    except ValueError as exc:
        raise AppError(code, f"computed {label} bounds are degenerate") from exc


def compute_candidate(
    profile: TemplateProfile,
    scale_candidate: ScaleCandidate,
    rotation: Rotation,
) -> FrameCandidate:
    """Reconstruct frame and approved Window using only a quarter-turn and translation."""

    rotation = _approved_rotation(rotation)
    if not _finite(profile.scale_anchor) or not _finite(scale_candidate.anchor):
        raise AppError("E307", "scale anchor contains non-finite coordinates")

    frame = _bounds(
        tuple(
            _transform(point, profile.scale_anchor, scale_candidate.anchor, rotation)
            for point in _corners(profile.frame)
        ),
        "E307",
        "frame",
    )
    plot_window = _bounds(
        tuple(
            _transform(point, profile.scale_anchor, scale_candidate.anchor, rotation)
            for point in _corners(profile.reference_window)
        ),
        "E309",
        "plot window",
    )
    return FrameCandidate(
        profile_id=profile.profile_id,
        scale_candidate=scale_candidate,
        rotation=rotation,
        frame=frame,
        plot_window=plot_window,
        residual=0.0,
    )
