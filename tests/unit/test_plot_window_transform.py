from dataclasses import replace
from pathlib import Path

import pytest

from dwg_to_pdf.domain import Point, Rect, ScaleCandidate
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.plot_window_transform import (
    compute_candidate,
    inverse_plot_rotation,
)
from dwg_to_pdf.templates.profile_store import load_profile


@pytest.mark.parametrize(
    ("rotation", "anchor", "expected_bounds", "plot_rotation"),
    [
        (0, Point(29250, 20850), ((10000, 20000), (31000, 34850)), 0),
        (90, Point(-850, 29250), ((-14850, 10000), (0, 31000)), 270),
        (180, Point(-19250, -850), ((-21000, -14850), (0, 0)), 180),
        (270, Point(850, -19250), ((0, -21000), (14850, 0)), 90),
    ],
)
def test_reconstructs_window_after_translation_and_rotation(
    rotation, anchor, expected_bounds, plot_rotation
) -> None:
    profile = load_profile(Path("tests/fixtures/profile_1_to_50.json"))

    candidate = compute_candidate(profile, ScaleCandidate(anchor, "1:50", "A1"), rotation)

    actual_bounds = (
        candidate.plot_window.lower_left.x,
        candidate.plot_window.lower_left.y,
        candidate.plot_window.upper_right.x,
        candidate.plot_window.upper_right.y,
    )
    assert actual_bounds == pytest.approx(expected_bounds[0] + expected_bounds[1])
    assert candidate.frame == candidate.plot_window
    assert candidate.scale_candidate.anchor == anchor
    assert inverse_plot_rotation(rotation) == plot_rotation


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), float("-inf")])
def test_rejects_nonfinite_target_anchor(coordinate: float) -> None:
    profile = load_profile(Path("tests/fixtures/profile_1_to_50.json"))

    with pytest.raises(AppError) as exc:
        compute_candidate(
            profile,
            ScaleCandidate(Point(coordinate, 0), "1:50", "A1"),
            0,
        )

    assert exc.value.code == "E307"


def test_rejects_nonfinite_computed_window() -> None:
    profile = load_profile(Path("tests/fixtures/profile_1_to_50.json"))
    unsafe_window = Rect(Point(float("nan"), 0), Point(21000, 14850))

    with pytest.raises(AppError) as exc:
        compute_candidate(
            replace(profile, reference_window=unsafe_window),
            ScaleCandidate(Point(19250, 850), "1:50", "A1"),
            0,
        )

    assert exc.value.code == "E309"


@pytest.mark.parametrize("rotation", [45, False])
def test_rejects_rotation_outside_four_approved_directions(rotation) -> None:
    profile = load_profile(Path("tests/fixtures/profile_1_to_50.json"))

    with pytest.raises(AppError) as exc:
        compute_candidate(
            profile,
            ScaleCandidate(Point(19250, 850), "1:50", "A1"),
            rotation,
        )

    assert exc.value.code == "E307"
