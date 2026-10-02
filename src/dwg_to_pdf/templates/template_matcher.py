from collections.abc import Sequence
import math

from ..domain import FrameCandidate, MatchDecision
from ..errors import AppError


def _valid_score(value: object, *, strictly_positive: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    lower_bound = 0 < value if strictly_positive else 0 <= value
    return math.isfinite(value) and lower_bound and value <= 1


def choose_unique(
    candidates: Sequence[tuple[FrameCandidate, float]],
    minimum_score: float,
    minimum_gap: float,
) -> MatchDecision:
    """Approve exactly one calibrated candidate, otherwise hold the drawing closed."""

    if not _valid_score(minimum_score, strictly_positive=True):
        raise AppError("E303", "matching score threshold is not calibrated")
    if not _valid_score(minimum_gap, strictly_positive=True):
        raise AppError("E304", "matching score gap is not calibrated")
    if not candidates:
        raise AppError("E303", "no frame candidate matched")
    if any(not _valid_score(score, strictly_positive=False) for _, score in candidates):
        raise AppError("E303", "frame candidate score is invalid")

    ranked = sorted(
        candidates,
        key=lambda item: (-item[1], item[0].scale_candidate.handle),
    )
    best, best_score = ranked[0]
    if best_score < minimum_score:
        raise AppError("E303", "best frame candidate is below the calibrated threshold")

    score_gap = best_score - ranked[1][1] if len(ranked) > 1 else 1.0
    if score_gap == 0.0:
        raise AppError("E304", "frame or rotation match is ambiguous")
    meets_gap = score_gap >= minimum_gap or math.isclose(
        score_gap,
        minimum_gap,
        rel_tol=1e-12,
        abs_tol=0.0,
    )
    if not math.isfinite(score_gap) or not meets_gap:
        raise AppError("E304", "frame or rotation match is ambiguous")
    return MatchDecision(best, best_score, score_gap)
