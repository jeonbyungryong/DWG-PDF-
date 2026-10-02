from decimal import Decimal
from pathlib import Path

import pytest

from dwg_to_pdf.domain import Point, Rect, ScaleCell, ScaleRatio, TemplateProfile
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.structural_fallback import (
    APPROVED_SCALE_KEYS,
    choose_profile_by_structure,
    profile_key,
    profiles_for_scale_cell,
)


def _profile(key: str) -> TemplateProfile:
    numerator, denominator = key.split(":")
    return TemplateProfile(
        profile_id=f"profile-{key.replace(':', '-')}",
        scale=ScaleRatio(Decimal(numerator), Decimal(denominator)),
        source_path=Path(f"{key.replace(':', '-')}.dwg"),
        source_sha256="A" * 64,
        approved=True,
        frame=Rect(Point(0, 0), Point(100, 50)),
        scale_anchor=Point(20, 10),
        scale_value_offset=Point(0, -5),
        scale_value_tolerance=0.5,
        orientation_anchor=Point(90, 5),
        reference_window=Rect(Point(0, 0), Point(100, 50)),
        position_tolerance=1.0,
    )


class FakeStore:
    def __init__(self, profiles):
        self.profiles = tuple(profiles)

    def all(self):
        return self.profiles

    def find(self, scale):
        for profile in self.profiles:
            if profile.scale == scale:
                return profile
        raise AppError("E300", "not found")


def _approved_profiles():
    return tuple(_profile(key) for key in APPROVED_SCALE_KEYS)


def _cell(state="na", token=None):
    return ScaleCell(Point(100, 50), state, token, "A1")


def test_approved_universe_is_exactly_the_required_thirteen() -> None:
    assert APPROVED_SCALE_KEYS == (
        "1:1", "1:2", "1:5", "1:10", "1:20", "1:50", "1:100",
        "2:1", "5:1", "10:1", "20:1", "50:1", "100:1",
    )


def test_valid_scale_returns_exactly_one_approved_profile() -> None:
    profiles = profiles_for_scale_cell(_cell("valid", " 1:50 "), FakeStore(_approved_profiles()))
    assert tuple(profile_key(item) for item in profiles) == ("1:50",)


def test_valid_scale_requires_production_ready_thirteen_profile_store() -> None:
    with pytest.raises(AppError) as raised:
        profiles_for_scale_cell(_cell("valid", "1:50"), FakeStore((_profile("1:50"),)))
    assert raised.value.code == "E300"


@pytest.mark.parametrize("state", ["blank", "na"])
def test_fallback_returns_all_and_only_thirteen_approved_profiles(state: str) -> None:
    profiles = profiles_for_scale_cell(_cell(state), FakeStore(reversed(_approved_profiles())))
    assert tuple(profile_key(item) for item in profiles) == APPROVED_SCALE_KEYS


@pytest.mark.parametrize(
    "profiles",
    [
        _approved_profiles()[:-1],
        _approved_profiles() + (_profile("1:25"),),
        _approved_profiles()[:-1] + (_profile("1:25"),),
    ],
)
def test_fallback_rejects_incomplete_or_out_of_universe_profiles(profiles) -> None:
    with pytest.raises(AppError) as raised:
        profiles_for_scale_cell(_cell(), FakeStore(profiles))
    assert raised.value.code == "E300"


def test_valid_scale_outside_approved_universe_is_rejected_even_if_store_contains_it() -> None:
    with pytest.raises(AppError) as raised:
        profiles_for_scale_cell(_cell("valid", "1:25"), FakeStore((_profile("1:25"),)))
    assert raised.value.code == "E305"


def test_malformed_valid_state_token_is_always_e305() -> None:
    with pytest.raises(AppError) as raised:
        profiles_for_scale_cell(_cell("valid", "UNKNOWN"), FakeStore(_approved_profiles()))
    assert raised.value.code == "E305"


def test_structure_selection_is_input_order_deterministic() -> None:
    profiles = _approved_profiles()
    def scorer(profile, candidate):
        return 0.99 if profile_key(profile) == "1:50" and candidate.rotation == 0 else 0.1

    forward = choose_profile_by_structure(_cell(), profiles, scorer, 0.95, 0.02)
    reverse = choose_profile_by_structure(_cell(), tuple(reversed(profiles)), scorer, 0.95, 0.02)

    assert forward.candidate.profile_id == reverse.candidate.profile_id == "profile-1-50"


def test_structure_selection_rejects_equal_best_scores_as_ambiguous() -> None:
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), _approved_profiles(), lambda p, c: 0.99, 0.95, 0.02)
    assert raised.value.code == "E304"


def test_valid_scale_and_unique_relative_direction_select_without_structure_query() -> None:
    seen = []

    def scorer(profile, candidate):
        seen.append(candidate.rotation)
        return 1.0

    cell = ScaleCell(Point(100, 50), "valid", "1:50", "A1", rotation_hint=270)
    decision = choose_profile_by_structure(
        cell,
        (_profile("1:50"),),
        scorer,
        1.0,
        1.0,
    )

    assert seen == []
    assert decision.candidate.rotation == 270
    assert (decision.score, decision.score_gap) == (1.0, 1.0)


def test_valid_scale_without_unique_direction_keeps_four_way_structure_verification() -> None:
    seen = []

    def scorer(profile, candidate):
        seen.append(candidate.rotation)
        return 1.0 if candidate.rotation == 0 else 0.0

    decision = choose_profile_by_structure(
        _cell("valid", "1:50"),
        (_profile("1:50"),),
        scorer,
        1.0,
        1.0,
    )

    assert seen == [0, 90, 180, 270]
    assert decision.candidate.rotation == 0


def test_structure_selection_rejects_insufficient_best_score_gap_as_ambiguous() -> None:
    profiles = _approved_profiles()
    def scorer(profile, candidate):
        key = profile_key(profile)
        if candidate.rotation != 0:
            return 0.1
        return 0.99 if key == "1:50" else (0.98 if key == "1:20" else 0.1)

    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), profiles, scorer, 0.95, 0.02)
    assert raised.value.code == "E304"


def test_structure_selection_maps_below_threshold_to_no_match() -> None:
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), _approved_profiles(), lambda p, c: 0.2, 0.95, 0.02)
    assert raised.value.code == "E310"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, True, "0.99"])
def test_structure_selection_rejects_invalid_scorer_values_strictly(score) -> None:
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), _approved_profiles(), lambda p, c: score, 0.95, 0.02)
    assert raised.value.code == "E303"


@pytest.mark.parametrize("gap", [0.0, -0.1, float("nan"), True, "0.02"])
def test_invalid_minimum_gap_is_configuration_error(gap) -> None:
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), _approved_profiles(), lambda p, c: 0.99, 0.95, gap)
    assert raised.value.code == "E303"


def test_scorer_exception_is_stable_e303() -> None:
    def scorer(profile, candidate):
        raise RuntimeError("details must not leak")
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), _approved_profiles(), scorer, 0.95, 0.02)
    assert raised.value.code == "E303"


def test_scorer_does_not_hide_system_exit() -> None:
    def scorer(profile, candidate):
        raise SystemExit(7)
    with pytest.raises(SystemExit):
        choose_profile_by_structure(_cell(), _approved_profiles(), scorer, 0.95, 0.02)


def test_structure_selection_rejects_nonclosed_profile_input() -> None:
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(_cell(), _approved_profiles()[:-1], lambda p, c: 0.99, 0.95, 0.02)
    assert raised.value.code == "E300"
