from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from dwg_to_pdf.domain import Point, Rect, ScaleCandidate, ScaleRatio, TemplateProfile
from dwg_to_pdf.gstarcad.template_detector import verify_rotation
from dwg_to_pdf.templates.plot_window_transform import compute_candidate
from dwg_to_pdf.templates.structural_signature import StructuralSignature


class BoundedDocument:
    ModelSpace = object()
    Blocks = object()

    def __init__(self, segments):
        self.segments = segments
        self.bounds = []

    def filtered_geometry_snapshots(self, bounds):
        assert bounds is not None
        self.bounds.append(bounds)
        return [{"type": "LINE", "start": (a.x, a.y), "end": (b.x, b.y)} for a, b in self.segments]


def _profile(signature) -> TemplateProfile:
    return TemplateProfile(
        "p", ScaleRatio(Decimal(1), Decimal(1)), Path("x"), "A" * 64, True,
        Rect(Point(0, 0), Point(100, 70)), Point(90, 10), Point(0, -2), 1,
        Point(90, 25), Rect(Point(0, 0), Point(100, 70)), 0.01,
        structural_signature=signature,
    )


def test_verify_rotation_uses_only_bounded_geometry_query() -> None:
    signature = StructuralSignature(
        ((Point(-90, -10), Point(10, -10)),
         (Point(10, -10), Point(10, 60)),
         (Point(10, 60), Point(-90, 60)),
         (Point(-90, 60), Point(-90, -10)),
         (Point(0, -10), Point(0, 15))),
        4, 1, Point(0, 15),
    )
    profile = _profile(signature)
    candidate = compute_candidate(profile, ScaleCandidate(Point(590, 310), "1:1", "L"), 0)
    target = signature.transformed(candidate.scale_candidate.anchor, profile.scale_anchor, 0)
    document = BoundedDocument(target)
    assert verify_rotation(document, profile, candidate) == 1.0
    assert document.bounds == [candidate.frame]
