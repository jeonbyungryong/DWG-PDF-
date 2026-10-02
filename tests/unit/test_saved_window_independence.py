from decimal import Decimal
from pathlib import Path

import pytest

from dwg_to_pdf.domain import Point, Rect, ScaleCandidate, ScaleRatio, TemplateProfile
from dwg_to_pdf.templates.plot_window_transform import compute_candidate


@pytest.mark.parametrize(
    ("ratio", "expected", "unrelated_saved"),
    [((1, 1), (420.0, 297.0), (148.08275862069, 98.3172413793104)),
     ((1, 50), (21000.0, 14850.0), (37280.0381465517, 31994.9784213362))],
)
def test_computed_window_is_independent_of_target_saved_window(ratio, expected, unrelated_saved) -> None:
    width, height = expected
    profile = TemplateProfile(
        "p", ScaleRatio(Decimal(ratio[0]), Decimal(ratio[1])), Path("x"), "A" * 64, True,
        Rect(Point(0, 0), Point(width, height)), Point(width - 10, 10), Point(0, -1), 1,
        Point(width - 5, 15), Rect(Point(0, 0), Point(width, height)), 1,
    )
    result = compute_candidate(profile, ScaleCandidate(profile.scale_anchor, "x", "1"), 0)
    assert (result.plot_window.width, result.plot_window.height) == expected
    assert (result.plot_window.width, result.plot_window.height) != pytest.approx(unrelated_saved)
