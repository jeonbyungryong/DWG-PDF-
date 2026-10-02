from __future__ import annotations

from collections.abc import Callable, Sequence
import math

from ..domain import MatchDecision, ScaleCandidate, ScaleCell, TemplateProfile
from ..errors import AppError
from .plot_window_transform import compute_candidate
from .profile_store import ProfileStore, require_canonical_profiles
from .scale_label import parse_internal_scale
from .scale_universe import APPROVED_SCALE_KEYS, APPROVED_SCALE_KEY_SET, scale_key
from .template_matcher import choose_unique

_APPROVED_INDEX = {key: index for index, key in enumerate(APPROVED_SCALE_KEYS)}


def profile_key(profile: TemplateProfile) -> str:
    return scale_key(profile.scale.numerator, profile.scale.denominator)


def _closed_profiles(profiles: Sequence[TemplateProfile]) -> tuple[TemplateProfile, ...]:
    return require_canonical_profiles(tuple(profiles))


def profiles_for_scale_cell(
    cell: ScaleCell,
    store: ProfileStore,
) -> tuple[TemplateProfile, ...]:
    if cell.state == "valid":
        if cell.token is None:
            raise AppError("E305", "valid Scale cell has no value")
        try:
            ratio = parse_internal_scale(cell.token)
        except AppError as exc:
            raise AppError("E305", f"unsupported Scale value: {cell.token.strip()}") from exc
        key = scale_key(ratio.numerator, ratio.denominator)
        if key not in APPROVED_SCALE_KEY_SET:
            raise AppError("E305", f"unsupported Scale value: {cell.token.strip()}")
        ready = _closed_profiles(store.all())
        profile = next((item for item in ready if item.scale == ratio), None)
        if profile is None:
            raise AppError("E300", f"no approved profile for {key}")
        if not profile.approved or profile_key(profile) != key:
            raise AppError("E300", f"no approved profile for {key}")
        return (profile,)
    if cell.state not in ("blank", "na") or cell.token is not None:
        raise AppError("E305", "invalid Scale cell state")
    return _closed_profiles(store.all())


def _valid_unit_interval(value: object, *, strictly_positive: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value) or value > 1:
        return False
    return value > 0 if strictly_positive else value >= 0


def choose_profile_by_structure(
    cell: ScaleCell,
    profiles: Sequence[TemplateProfile],
    scorer: Callable[[TemplateProfile, object], float],
    minimum_score: float,
    minimum_gap: float,
) -> MatchDecision:
    """Score a canonical closed fallback universe without embedding calibration."""

    if not _valid_unit_interval(minimum_score, strictly_positive=True):
        raise AppError("E303", "matching score threshold is not calibrated")
    if not _valid_unit_interval(minimum_gap, strictly_positive=True):
        raise AppError("E303", "matching score gap is not calibrated")

    if cell.state in ("blank", "na"):
        ordered = _closed_profiles(profiles)
    elif cell.state == "valid" and cell.token is not None and len(profiles) == 1:
        try:
            expected = parse_internal_scale(cell.token)
        except AppError as exc:
            raise AppError("E305", f"unsupported Scale value: {cell.token.strip()}") from exc
        profile = profiles[0]
        if profile.scale != expected or profile_key(profile) not in _APPROVED_INDEX or not profile.approved:
            raise AppError("E300", "valid Scale profile is inconsistent")
        ordered = (profile,)
    else:
        raise AppError("E305", "invalid Scale cell state for structural matching")

    if cell.rotation_hint is not None and cell.rotation_hint not in (0, 90, 180, 270):
        raise AppError("E303", "Scale-cell rotation hint is invalid")
    if cell.state == "valid" and cell.rotation_hint is not None:
        profile = ordered[0]
        candidate = compute_candidate(
            profile,
            ScaleCandidate(cell.anchor, profile_key(profile), cell.handle),
            cell.rotation_hint,
        )
        return MatchDecision(candidate, 1.0, 1.0)
    rotations = (cell.rotation_hint,) if cell.rotation_hint is not None else (0, 90, 180, 270)

    scored = []
    for profile in ordered:
        for rotation in rotations:
            candidate = compute_candidate(
                profile,
                ScaleCandidate(cell.anchor, profile_key(profile), cell.handle),
                rotation,
            )
            try:
                score = scorer(profile, candidate)
            except Exception as exc:
                raise AppError("E303", "frame candidate scoring failed") from exc
            if not _valid_unit_interval(score, strictly_positive=False):
                raise AppError("E303", "frame candidate score is invalid")
            scored.append((candidate, float(score)))

    best_score = max(score for _, score in scored)
    if best_score < minimum_score:
        raise AppError("E310", "no approved template structure matched")
    return choose_unique(scored, minimum_score, minimum_gap)
