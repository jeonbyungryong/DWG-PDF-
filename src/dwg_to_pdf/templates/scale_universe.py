from decimal import Decimal

APPROVED_SCALE_KEYS = (
    "1:1",
    "1:2",
    "1:5",
    "1:10",
    "1:20",
    "1:50",
    "1:100",
    "2:1",
    "5:1",
    "10:1",
    "20:1",
    "50:1",
    "100:1",
)
APPROVED_SCALE_KEY_SET = frozenset(APPROVED_SCALE_KEYS)


def decimal_key(value: Decimal) -> str:
    raw = format(value, "f")
    return raw.rstrip("0").rstrip(".") if "." in raw else raw


def scale_key(numerator: Decimal, denominator: Decimal) -> str:
    return f"{decimal_key(numerator)}:{decimal_key(denominator)}"
