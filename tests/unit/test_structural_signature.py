from __future__ import annotations

from decimal import Decimal
import math
from pathlib import Path

import pytest

from dwg_to_pdf.domain import FrameCandidate, Point, Rect, ScaleCandidate, ScaleRatio, TemplateProfile
from dwg_to_pdf.templates.structural_signature import StructuralSignature, score_signature


def _signature() -> StructuralSignature:
    return StructuralSignature(
        segments=(
            (Point(-90, -10), Point(10, -10)),
            (Point(10, -10), Point(10, 60)),
            (Point(10, 60), Point(-90, 60)),
            (Point(-90, 60), Point(-90, -10)),
            (Point(0, -10), Point(0, 5)),
        ),
        frame_segment_count=4,
        title_segment_count=1,
        orientation_anchor=Point(0, 5),
    )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("translation", [Point(500, 300), Point(-125, 760), Point(0, -900)])
def test_signature_scores_exact_xy_translation_and_four_rotations(rotation: int, translation: Point) -> None:
    signature = _signature()
    target = signature.transformed(translation, Point(0, 0), rotation)
    assert score_signature(signature, target, translation, Point(0, 0), rotation, 0.01) == 1.0


def test_signature_fails_closed_for_missing_anchor_mirror_and_45_degree() -> None:
    signature = _signature()
    exact = list(signature.transformed(Point(0, 0), Point(0, 0), 0))
    assert score_signature(signature, exact[:-1], Point(0, 0), Point(0, 0), 0, 0.01) < 1.0
    mirrored = tuple((Point(-a.x, a.y), Point(-b.x, b.y)) for a, b in exact)
    assert score_signature(signature, mirrored, Point(0, 0), Point(0, 0), 0, 0.01) < 1.0
    with pytest.raises(ValueError):
        signature.transformed(Point(0, 0), Point(0, 0), 45)


def test_signature_scores_wrong_frame_size_below_exact_match() -> None:
    signature = _signature()
    scaled = tuple(
        (Point(a.x * 2, a.y * 2), Point(b.x * 2, b.y * 2))
        for a, b in signature.transformed(Point(0, 0), Point(0, 0), 0)
    )
    assert score_signature(signature, scaled, Point(0, 0), Point(0, 0), 0, 0.01) < 1.0


def test_signature_rejects_nonfinite_geometry() -> None:
    with pytest.raises(ValueError):
        StructuralSignature(((Point(math.nan, 0), Point(1, 0)),), 1, 0, Point(0, 0))
