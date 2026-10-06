"""The live regression comparator tolerates roundoff, not changed decisions."""
import importlib.util
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from dwg_to_pdf.domain import ConversionOutcome, ConvertedFrame, Point, Rect, ScaleRatio


path = Path(__file__).resolve().parents[2] / "tools/regression/gstarcad/test_gstar_regression.py"
spec = importlib.util.spec_from_file_location("gstar_decision_regression", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def outcome(window=(0.0, 0.0, 420.0, 297.0)):
    frame = ConvertedFrame(
        Path("off/drawing.pdf"), ScaleRatio(Decimal("1"), Decimal("1")), 0,
        Rect(Point(*window[:2]), Point(*window[2:])),
    )
    return ConversionOutcome(Path("drawing.dwg"), (frame,))


def compare(left, right):
    comparator = getattr(module, "assert_matching_decisions", None)
    assert callable(comparator), "the regression needs a tolerance-aware decision comparator"
    comparator(left, right)


def test_accepts_roundoff_and_different_output_directories():
    left = outcome()
    right = outcome((7.275957614183426e-12, 0.0, 420.0, 297.0))
    right = replace(right, frames=(replace(right.frames[0], output=Path("on/drawing.pdf")),))
    compare([left], [right])


@pytest.mark.parametrize("delta", [0.000999, -0.000999])
def test_accepts_coordinate_difference_below_approved_limit(delta):
    compare([outcome()], [outcome((delta, 0.0, 420.0, 297.0))])


@pytest.mark.parametrize("coordinate", range(4))
@pytest.mark.parametrize("delta", [0.001, -0.001, 0.01])
def test_rejects_difference_at_or_above_limit(coordinate, delta):
    # Zero coordinates keep the exact boundary independent of subtraction rounding.
    window = [-420.0, -297.0, 0.0, 0.0] if coordinate >= 2 else [0.0, 0.0, 420.0, 297.0]
    changed = window.copy()
    changed[coordinate] += delta
    with pytest.raises(AssertionError):
        compare([outcome(window)], [outcome(changed)])


@pytest.mark.parametrize("coordinate", range(4))
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_rejects_nonfinite_coordinates_even_when_both_sides_equal(coordinate, invalid):
    base = outcome()
    # Bypass Rect's ordering guard only to exercise malformed recorded decisions.
    rect = object.__new__(Rect)
    coordinates = [0.0, 0.0, 420.0, 297.0]
    coordinates[coordinate] = invalid
    object.__setattr__(rect, "lower_left", Point(*coordinates[:2]))
    object.__setattr__(rect, "upper_right", Point(*coordinates[2:]))
    malformed = replace(base, frames=(replace(base.frames[0], plot_window=rect),))
    with pytest.raises(AssertionError):
        compare([malformed], [malformed])


@pytest.mark.parametrize("change", ["scale", "rotation", "source", "count", "frames", "order"])
def test_rejects_changed_discrete_decisions_and_result_shape(change):
    left = outcome()
    other = replace(left, source=Path("other.dwg"))
    right = left
    if change == "scale":
        right = replace(left, frames=(replace(left.frames[0], scale=ScaleRatio(Decimal("2"), Decimal("1"))),))
    elif change == "rotation":
        right = replace(left, frames=(replace(left.frames[0], rotation=90),))
    elif change == "source":
        right = other
    elif change == "frames":
        right = replace(left, frames=())
    with pytest.raises(AssertionError):
        compare([left, other] if change == "order" else [left],
                [other, left] if change == "order" else [] if change == "count" else [right])
