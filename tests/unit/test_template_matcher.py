from pathlib import Path

import pytest

from dwg_to_pdf.domain import Point, ScaleCandidate
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.plot_window_transform import compute_candidate
from dwg_to_pdf.templates.profile_store import load_profile
from dwg_to_pdf.templates.template_matcher import choose_unique


def _candidate(handle: str):
    profile = load_profile(Path("tests/fixtures/profile_1_to_50.json"))
    return compute_candidate(
        profile,
        ScaleCandidate(Point(19250, 850), "1:50", handle),
        0,
    )


def test_ambiguous_rotation_is_held() -> None:
    with pytest.raises(AppError) as exc:
        choose_unique(
            [(_candidate("A1"), 0.95), (_candidate("A2"), 0.94)],
            minimum_score=0.90,
            minimum_gap=0.02,
        )

    assert exc.value.code == "E304"


@pytest.mark.parametrize("handles", [("A1", "B2"), ("B2", "A1")])
def test_exact_top_score_tie_is_held_for_tiny_positive_gap(handles) -> None:
    with pytest.raises(AppError) as exc:
        choose_unique(
            [(_candidate(handle), 0.95) for handle in handles],
            minimum_score=0.90,
            minimum_gap=1e-16,
        )

    assert exc.value.code == "E304"


@pytest.mark.parametrize("reverse", [False, True])
def test_approves_same_non_tied_best_candidate_regardless_of_input_order(reverse) -> None:
    best = _candidate("B2")
    candidates = [(_candidate("A1"), 0.90), (best, 0.95)]
    decision = choose_unique(
        list(reversed(candidates)) if reverse else candidates,
        minimum_score=0.90,
        minimum_gap=0.05,
    )

    assert decision.candidate is best
    assert decision.score == pytest.approx(0.95)
    assert decision.score_gap == pytest.approx(0.05)


@pytest.mark.parametrize("candidates", [[], [(_candidate("A1"), 0.89)]])
def test_missing_or_below_threshold_candidate_is_held(candidates) -> None:
    with pytest.raises(AppError) as exc:
        choose_unique(candidates, minimum_score=0.90, minimum_gap=0.02)

    assert exc.value.code == "E303"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_candidate_score_is_held(score: float) -> None:
    with pytest.raises(AppError):
        choose_unique(
            [(_candidate("A1"), score)],
            minimum_score=0.90,
            minimum_gap=0.02,
        )


@pytest.mark.parametrize(
    ("minimum_score", "minimum_gap"),
    [
        (float("nan"), 0.02),
        (0.90, float("inf")),
        (0.0, 0.02),
        (0.90, 0.0),
    ],
)
def test_uncalibrated_thresholds_are_held(minimum_score: float, minimum_gap: float) -> None:
    with pytest.raises(AppError):
        choose_unique(
            [(_candidate("A1"), 0.95)],
            minimum_score=minimum_score,
            minimum_gap=minimum_gap,
        )
