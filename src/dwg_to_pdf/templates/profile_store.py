from decimal import Decimal
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import validate

from ..domain import Point, Rect, ScaleRatio, TemplateProfile
from ..errors import AppError
from .profile_schema import PROFILE_SCHEMA
from .scale_universe import APPROVED_SCALE_KEYS, APPROVED_SCALE_KEY_SET, scale_key
from .structural_signature import signature_from_raw


def _reject_nonstandard_constant(value: str) -> NoReturn:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _finite_number(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("profile geometry and tolerance values must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("profile geometry and tolerance values must be finite")
    return number


def _finite_positive_number(value: object) -> float:
    number = _finite_number(value)
    if number <= 0:
        raise ValueError("profile tolerance values must be positive")
    return number


def _point(value: list[object]) -> Point:
    return Point(_finite_number(value[0]), _finite_number(value[1]))


def _rect(value: list[list[object]]) -> Rect:
    return Rect(_point(value[0]), _point(value[1]))


def load_profile(path: Path) -> TemplateProfile:
    """Load one schema-valid, explicitly approved template profile."""

    try:
        raw: dict[str, Any] = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_constant,
        )
        validate(raw, PROFILE_SCHEMA)
        source_path = Path(raw["source"]["path"])
        if source_path.is_absolute() or source_path.drive or ".." in source_path.parts:
            raise ValueError("profile source path must be portable and relative")
        return TemplateProfile(
            profile_id=raw["profile_id"],
            scale=ScaleRatio(
                Decimal(raw["scale"]["numerator"]),
                Decimal(raw["scale"]["denominator"]),
            ),
            source_path=source_path,
            source_sha256=raw["source"]["sha256"],
            approved=True,
            frame=_rect(raw["frame"]),
            scale_anchor=_point(raw["scale_anchor"]),
            scale_value_offset=_point(raw["scale_value_offset"]),
            scale_value_tolerance=_finite_positive_number(raw["scale_value_tolerance"]),
            orientation_anchor=_point(raw["orientation_anchor"]),
            reference_window=_rect(raw["reference_window"]),
            position_tolerance=_finite_positive_number(raw["position_tolerance"]),
            structural_signature=signature_from_raw(raw["structural_signature"]),
        )
    except Exception as exc:
        raise AppError("E308", f"invalid or unapproved profile: {path.name}", path) from exc


def require_canonical_profiles(profiles: tuple[TemplateProfile, ...]) -> tuple[TemplateProfile, ...]:
    """Fail closed unless every approved Scale profile is present exactly once."""

    by_key: dict[str, TemplateProfile] = {}
    for profile in profiles:
        key = scale_key(profile.scale.numerator, profile.scale.denominator)
        if not profile.approved or key not in APPROVED_SCALE_KEY_SET or key in by_key:
            raise AppError("E300", "exactly 13 approved template profiles are required")
        by_key[key] = profile
    if len(by_key) != len(APPROVED_SCALE_KEYS) or set(by_key) != APPROVED_SCALE_KEY_SET:
        raise AppError("E300", "exactly 13 approved template profiles are required")
    return tuple(by_key[key] for key in APPROVED_SCALE_KEYS)


class ProfileStore:
    def __init__(self, directory: Path, *, source_root: Path) -> None:
        self.directory = directory
        self.source_root = source_root.resolve(strict=True)
        self._profiles: dict[ScaleRatio, TemplateProfile] = {}

    def load_all(self) -> None:
        profiles = [load_profile(path) for path in sorted(self.directory.glob("*.json"))]
        keys = [scale_key(profile.scale.numerator, profile.scale.denominator) for profile in profiles]
        if len(keys) != len(set(keys)):
            raise AppError("E308", "duplicate approved profile scale")
        unsupported = sorted(set(keys) - APPROVED_SCALE_KEY_SET)
        if unsupported:
            raise AppError("E308", f"profile scale is outside the approved universe: {unsupported}")
        resolved_profiles = []
        for profile in profiles:
            resolved_source = (self.source_root / profile.source_path).resolve(strict=False)
            try:
                resolved_source.relative_to(self.source_root)
            except ValueError as exc:
                raise AppError("E308", "profile source escapes explicit source root") from exc
            if not resolved_source.exists():
                raise AppError(
                    "E308",
                    f"reference DWG is missing: {resolved_source}",
                    resolved_source,
                )
            actual = hashlib.sha256(resolved_source.read_bytes()).hexdigest()
            if actual.casefold() != profile.source_sha256.casefold():
                raise AppError(
                    "E308",
                    f"reference DWG hash changed: {resolved_source}",
                    resolved_source,
                )
            resolved_profiles.append(replace(profile, source_path=resolved_source))
        self._profiles = {profile.scale: profile for profile in resolved_profiles}

    def find(self, scale: ScaleRatio) -> TemplateProfile:
        try:
            return self._profiles[scale]
        except KeyError as exc:
            raise AppError("E300", f"no approved profile for {scale}") from exc

    def all(self) -> tuple[TemplateProfile, ...]:
        """Return a deterministic immutable snapshot of verified profiles."""

        return tuple(
            sorted(
                self._profiles.values(),
                key=lambda profile: (
                    profile.scale.numerator / profile.scale.denominator,
                    profile.scale.numerator,
                    profile.scale.denominator,
                    profile.profile_id,
                ),
            )
        )
