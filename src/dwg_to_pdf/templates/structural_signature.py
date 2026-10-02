from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from ..domain import Point, Rotation
from .plot_window_transform import rotate

Segment = tuple[Point, Point]


def _finite(point: Point) -> bool:
    return math.isfinite(point.x) and math.isfinite(point.y)


def _ordered(segment: Segment) -> Segment:
    a, b = segment
    return (a, b) if (a.x, a.y) <= (b.x, b.y) else (b, a)


@dataclass(frozen=True)
class StructuralSignature:
    """Finite linework relative to the registered Scale-label anchor."""

    segments: tuple[Segment, ...]
    frame_segment_count: int
    title_segment_count: int
    orientation_anchor: Point

    def __post_init__(self) -> None:
        if not self.segments or not all(_finite(a) and _finite(b) and a != b for a, b in self.segments):
            raise ValueError("structural signature requires finite non-degenerate segments")
        if self.frame_segment_count < 4 or self.title_segment_count < 1:
            raise ValueError("structural signature requires frame and title geometry")
        if self.frame_segment_count + self.title_segment_count > len(self.segments):
            raise ValueError("structural signature counts exceed stored segments")
        if not _finite(self.orientation_anchor):
            raise ValueError("orientation anchor must be finite")

    def transformed(
        self,
        target_scale_anchor: Point,
        reference_scale_anchor: Point,
        rotation: Rotation,
    ) -> tuple[Segment, ...]:
        del reference_scale_anchor  # points are already stored relative to this anchor
        if isinstance(rotation, bool) or rotation not in (0, 90, 180, 270):
            raise ValueError("structural signature rotation must be a quarter turn")

        def transform(point: Point) -> Point:
            turned = rotate(point, rotation)
            return Point(target_scale_anchor.x + turned.x, target_scale_anchor.y + turned.y)

        return tuple(_ordered((transform(a), transform(b))) for a, b in self.segments)


def _segment_distance(left: Segment, right: Segment) -> float:
    left = _ordered(left)
    right = _ordered(right)
    return max(
        math.hypot(left[0].x - right[0].x, left[0].y - right[0].y),
        math.hypot(left[1].x - right[1].x, left[1].y - right[1].y),
    )


def score_signature(
    signature: StructuralSignature,
    observed: Iterable[Segment],
    target_scale_anchor: Point,
    reference_scale_anchor: Point,
    rotation: Rotation,
    tolerance: float,
) -> float:
    if isinstance(tolerance, bool) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("signature tolerance must be finite and positive")
    expected = signature.transformed(target_scale_anchor, reference_scale_anchor, rotation)
    actual = tuple(_ordered(item) for item in observed)
    if any(not (_finite(a) and _finite(b) and a != b) for a, b in actual):
        raise ValueError("observed structure contains invalid geometry")
    unmatched = list(actual)
    matches = 0
    for segment in expected:
        candidates = [(_segment_distance(segment, other), index) for index, other in enumerate(unmatched)]
        if not candidates:
            continue
        distance, index = min(candidates, key=lambda item: (item[0], item[1]))
        if distance <= tolerance:
            matches += 1
            unmatched.pop(index)
    score = matches / len(expected)
    return float(min(1.0, max(0.0, score)))


def signature_from_raw(raw: dict[str, object]) -> StructuralSignature:
    segments = tuple(
        (Point(float(item[0][0]), float(item[0][1])), Point(float(item[1][0]), float(item[1][1])))
        for item in raw["segments"]
    )
    return StructuralSignature(
        segments=segments,
        frame_segment_count=int(raw["frame_segment_count"]),
        title_segment_count=int(raw["title_segment_count"]),
        orientation_anchor=Point(float(raw["orientation_anchor"][0]), float(raw["orientation_anchor"][1])),
    )


def signature_to_raw(signature: StructuralSignature) -> dict[str, object]:
    return {
        "segments": [[[a.x, a.y], [b.x, b.y]] for a, b in signature.segments],
        "frame_segment_count": signature.frame_segment_count,
        "title_segment_count": signature.title_segment_count,
        "orientation_anchor": [signature.orientation_anchor.x, signature.orientation_anchor.y],
    }
