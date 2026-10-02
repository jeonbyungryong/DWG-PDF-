from decimal import Decimal
from pathlib import Path

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.scale_label import parse_internal_scale, parse_reference_filename


def test_reference_filename_and_internal_token_agree() -> None:
    expected = (Decimal("1"), Decimal("50"))
    ref = parse_reference_filename(Path("TEMPLETE_1대50.DWG"))
    internal = parse_internal_scale(" 1 : 50 ")
    assert (ref.numerator, ref.denominator) == expected
    assert internal == ref


def test_work_filename_is_not_a_valid_reference_name() -> None:
    with pytest.raises(AppError) as exc:
        parse_reference_filename(Path("XXX_1대50_PART.DWG"))
    assert exc.value.code == "E305"


@pytest.mark.parametrize("token", ["1:50_PART", "1/50", "0:50", "1:0"])
def test_invalid_internal_scale_is_rejected(token: str) -> None:
    with pytest.raises(AppError) as exc:
        parse_internal_scale(token)
    assert exc.value.code == "E303"
