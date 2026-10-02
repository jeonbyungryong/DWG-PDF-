from decimal import Decimal
from pathlib import Path

import pytest

from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.domain import Point, Rect, ScaleRatio
from dwg_to_pdf.errors import AppError


def _config_text(
    *,
    gstarcad: str = 'prog_id="GStarCAD.Application.26"',
    matching: str = "auto_match_enabled=false\nuse_target_saved_window=false",
    plot: str = (
        'plotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\n'
        'media_height_mm=210.0\nstyle_sheet="monochrome.ctb"'
    ),
) -> str:
    return f"[gstarcad]\n{gstarcad}\n[matching]\n{matching}\n[plot]\n{plot}\n"


def _assert_e001(path: Path) -> None:
    with pytest.raises(AppError) as exc:
        load_config(path)
    assert exc.value.code == "E001"
    assert exc.value.path == path


def test_scale_ratio_returns_expected_a3_model_size() -> None:
    assert ScaleRatio(Decimal("1"), Decimal("50")).a3_model_size() == (
        Decimal("21000"), Decimal("14850")
    )


def test_rect_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError, match="rect bounds"):
        Rect(Point(10, 0), Point(0, 10))


def test_config_rejects_saved_target_window(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        '[gstarcad]\nprog_id="GStarCAD.Application.26"\n'
        '[matching]\nauto_match_enabled=false\nuse_target_saved_window=true\n'
        '[plot]\nplotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\n'
        'media_height_mm=210.0\nstyle_sheet="monochrome.ctb"\n',
        encoding="utf-8",
    )
    with pytest.raises(AppError) as exc:
        load_config(path)
    assert exc.value.code == "E001"


@pytest.mark.parametrize(
    "plot",
    [
        'plotter_name="Other PDF.pc3"\nmedia_width_mm=297.0\nmedia_height_mm=210.0\nstyle_sheet="monochrome.ctb"',
        'plotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\nmedia_height_mm=210.0\nstyle_sheet="color.ctb"',
    ],
    ids=["unapproved-plotter", "unapproved-style-sheet"],
)
def test_config_rejects_unapproved_fixed_plot_contract_before_com(tmp_path: Path, plot: str) -> None:
    path = tmp_path / "unapproved-plot.toml"
    path.write_text(_config_text(plot=plot), encoding="utf-8")

    _assert_e001(path)


def test_config_accepts_case_insensitive_approved_monochrome_style_sheet(tmp_path: Path) -> None:
    path = tmp_path / "approved-case.toml"
    path.write_text(
        _config_text(
            plot=(
                'plotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\n'
                'media_height_mm=210.0\nstyle_sheet="MONOCHROME.CTB"'
            )
        ),
        encoding="utf-8",
    )

    assert load_config(path).style_sheet == "MONOCHROME.CTB"


def test_config_rejects_string_auto_match_boolean(tmp_path: Path) -> None:
    path = tmp_path / "string-bool.toml"
    path.write_text(
        _config_text(
            matching=(
                'auto_match_enabled="false"\nuse_target_saved_window=false\n'
                "matching_threshold=0.8\nminimum_score_gap=0.1"
            )
        ),
        encoding="utf-8",
    )
    _assert_e001(path)


@pytest.mark.parametrize("enabled", [True, False])
def test_native_extraction_can_be_explicitly_selected(tmp_path, enabled):
    path = tmp_path / "native.toml"
    path.write_text(_config_text(matching="auto_match_enabled=false\nuse_native_extraction=" + str(enabled).lower()), encoding="utf-8")
    assert load_config(path).use_native_extraction is enabled


def test_native_extraction_rejects_a_string_boolean(tmp_path):
    path = tmp_path / "native.toml"
    path.write_text(_config_text(matching='auto_match_enabled=false\nuse_native_extraction="false"'), encoding="utf-8")
    _assert_e001(path)


@pytest.mark.parametrize("field", ["matching_threshold", "minimum_score_gap"])
@pytest.mark.parametrize("value", ["true", "-0.1", "0.0", "nan", "inf", "1.1"])
def test_config_rejects_invalid_enabled_score(
    tmp_path: Path, field: str, value: str
) -> None:
    path = tmp_path / f"bad-{field}-{value}.toml"
    other = "minimum_score_gap" if field == "matching_threshold" else "matching_threshold"
    path.write_text(
        _config_text(
            matching=(
                "auto_match_enabled=true\nuse_target_saved_window=false\n"
                f"{field}={value}\n{other}=0.1"
            )
        ),
        encoding="utf-8",
    )
    _assert_e001(path)


def test_config_normalizes_malformed_toml(tmp_path: Path) -> None:
    path = tmp_path / "malformed.toml"
    path.write_text("[matching\nauto_match_enabled=false", encoding="utf-8")
    _assert_e001(path)


def test_config_normalizes_wrong_section_type(tmp_path: Path) -> None:
    path = tmp_path / "wrong-section.toml"
    path.write_text(
        'matching=1\n[gstarcad]\nprog_id="GStarCAD.Application.26"\n'
        '[plot]\nplotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\n'
        'media_height_mm=210.0\nstyle_sheet="monochrome.ctb"\n',
        encoding="utf-8",
    )
    _assert_e001(path)


@pytest.mark.parametrize(
    "content",
    [
        '[gstarcad]\nprog_id="GStarCAD.Application.26"\n',
        _config_text(gstarcad=""),
        _config_text(matching="use_target_saved_window=false"),
        _config_text(plot='plotter_name="DWG To PDF.pc3"'),
    ],
    ids=["missing-sections", "missing-prog-id", "missing-auto-match", "missing-plot-keys"],
)
def test_config_normalizes_missing_sections_and_keys(tmp_path: Path, content: str) -> None:
    path = tmp_path / "missing.toml"
    path.write_text(content, encoding="utf-8")
    _assert_e001(path)


@pytest.mark.parametrize(
    ("section", "content"),
    [
        ("gstarcad", "prog_id=26"),
        ("plot", "plotter_name=42\nmedia_width_mm=297.0\nmedia_height_mm=210.0\nstyle_sheet=\"monochrome.ctb\""),
        ("plot", 'plotter_name="DWG To PDF.pc3"\nmedia_width_mm="297"\nmedia_height_mm=210.0\nstyle_sheet="monochrome.ctb"'),
        ("plot", 'plotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\nmedia_height_mm=210.0\nstyle_sheet=42'),
        ("plot", 'plotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\nmedia_height_mm=210.0\nstyle_sheet="monochrome.ctb"\npreferred_media_names="User77"'),
    ],
    ids=["prog-id", "plotter", "media-size", "style-sheet", "preferred-media"],
)
def test_config_normalizes_wrong_field_types(
    tmp_path: Path, section: str, content: str
) -> None:
    path = tmp_path / "wrong-type.toml"
    kwargs = {section: content}
    path.write_text(_config_text(**kwargs), encoding="utf-8")
    _assert_e001(path)
