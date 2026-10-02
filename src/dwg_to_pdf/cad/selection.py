from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal

from ..errors import AppError

ProviderId = Literal["gstarcad", "autocad"]


@dataclass(frozen=True)
class CadSelection:
    provider: ProviderId
    prog_id: str | None
    allow_experimental_autocad: bool


@dataclass(frozen=True)
class CadCandidate:
    provider: ProviderId
    prog_id: str
    clsid: str
    executable: Path
    product_name: str
    reported_version: str | None


def validate_prog_id(prog_id: object, provider: ProviderId) -> str:
    prefix = {"gstarcad": "GStarCAD", "autocad": "AutoCAD"}.get(provider)
    if prefix is None or not isinstance(prog_id, str) or not re.fullmatch(
        rf"{prefix}\.Application(?:\.[0-9]+)*", prog_id, re.IGNORECASE
    ):
        raise AppError("E001", f"{provider}: invalid or mismatched CAD ProgID")
    return prog_id


def select_candidate(selection: CadSelection, candidates: tuple[CadCandidate, ...]) -> CadCandidate:
    if selection.provider not in ("gstarcad", "autocad") or type(selection.allow_experimental_autocad) is not bool:
        raise AppError("E001", "invalid CAD selection")
    if selection.provider == "autocad" and not selection.allow_experimental_autocad:
        raise AppError("E222", "AutoCAD: experimental support requires explicit opt-in")
    matching = tuple(item for item in candidates if item.provider == selection.provider)
    registrations: dict[str, CadCandidate] = {}
    identities: dict[tuple[str, str], CadCandidate] = {}
    for item in sorted(matching, key=lambda item: (item.prog_id.count("."), item.prog_id.casefold()), reverse=True):
        identity = (item.clsid.casefold(), str(item.executable).casefold())
        key = item.prog_id.casefold()
        existing = registrations.get(key)
        if existing and (existing.clsid.casefold(), str(existing.executable).casefold()) != identity:
            raise AppError("E202", f"{selection.provider}: conflicting registration; repair CAD registration")
        registrations[key] = item
        identities.setdefault(identity, item)
    if selection.prog_id is not None:
        validate_prog_id(selection.prog_id, selection.provider)
        selected = registrations.get(selection.prog_id.casefold())
        if selected is None:
            raise AppError("E202", f"{selection.provider}: selected ProgID is not an installed candidate")
        return selected
    if not identities:
        raise AppError("E220", f"{selection.provider}: no installed CAD candidate; check installation")
    if len(identities) != 1:
        raise AppError("E221", f"{selection.provider}: multiple CAD candidates; select a ProgID explicitly")
    return next(iter(identities.values()))
