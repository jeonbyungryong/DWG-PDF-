from pathlib import Path

import pytest

from dwg_to_pdf.output_planner import output_names


def test_output_names_uses_no_scale_suffix_and_numbered_extra_frames() -> None:
    assert output_names(Path("A.dwg"), 3) == ("A.pdf", "A_2.pdf", "A_3.pdf")


@pytest.mark.parametrize("frame_count", [True, 1.5])
def test_output_names_rejects_boolean_or_non_integer_frame_counts(frame_count: object) -> None:
    with pytest.raises(ValueError):
        output_names(Path("A.dwg"), frame_count)  # type: ignore[arg-type]


def test_output_names_returns_empty_tuple_for_no_frames() -> None:
    assert output_names(Path("A.dwg"), 0) == ()
