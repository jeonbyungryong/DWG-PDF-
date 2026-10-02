from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from ..domain import ScaleRatio
from ..errors import AppError

REFERENCE = re.compile(
    r"^(?:(?:TEMPLETE|TEMPLATE)_)?(?P<n>\d+(?:\.\d+)?)대(?P<d>\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)
INTERNAL = re.compile(
    r"^\s*(?P<n>\d+(?:\.\d+)?)\s*(?::|대)\s*(?P<d>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


def _ratio(match: re.Match[str] | None, code: str, raw: str) -> ScaleRatio:
    if match is None:
        raise AppError(code, f"invalid scale token: {raw}")
    try:
        return ScaleRatio(Decimal(match.group("n")), Decimal(match.group("d")))
    except (InvalidOperation, ValueError) as exc:
        raise AppError(code, f"invalid scale token: {raw}") from exc


def parse_reference_filename(path: Path) -> ScaleRatio:
    """Parse only a registered reference naming convention, never a work filename."""

    return _ratio(REFERENCE.fullmatch(path.stem), "E305", path.name)


def parse_internal_scale(text: str) -> ScaleRatio:
    """Parse a scale token discovered inside a drawing."""

    return _ratio(INTERNAL.fullmatch(text), "E303", text)
