from pathlib import Path

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.input_resolver import resolve_inputs


def test_resolve_inputs_collects_direct_dwg_files_deduplicates_and_sorts(tmp_path: Path) -> None:
    folder = tmp_path / "batch"
    folder.mkdir()
    first = folder / "b.DWG"
    second = folder / "a.dwg"
    nested = folder / "nested"
    nested.mkdir()
    skipped = nested / "hidden.dwg"
    for path in (first, second, skipped):
        path.write_bytes(b"dwg")

    assert resolve_inputs([first, folder, second]) == (
        second.resolve(),
        first.resolve(),
    )


def test_resolve_inputs_rejects_an_empty_selection(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(AppError) as raised:
        resolve_inputs([empty])

    assert raised.value.code == "E100"


def test_resolve_inputs_rejects_requested_symlink_before_resolving(tmp_path: Path) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    link = tmp_path / "link.dwg"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation unavailable in this environment")

    with pytest.raises(AppError) as raised:
        resolve_inputs([link])

    assert raised.value.code == "E100"
    assert raised.value.path == link


def test_resolve_inputs_rejects_reparse_child_before_resolving(
    monkeypatch, tmp_path: Path
) -> None:
    folder = tmp_path / "batch"
    folder.mkdir()
    drawing = folder / "drawing.dwg"
    drawing.write_bytes(b"dwg")

    monkeypatch.setattr(
        "dwg_to_pdf.input_resolver._is_reparse_point",
        lambda path: Path(path) == drawing,
    )

    with pytest.raises(AppError) as raised:
        resolve_inputs([folder])

    assert raised.value.code == "E100"
    assert raised.value.path == drawing


def test_resolve_inputs_rejects_requested_reparse_point_before_directory_iteration(
    monkeypatch, tmp_path: Path
) -> None:
    folder = tmp_path / "batch"
    folder.mkdir()
    monkeypatch.setattr(
        "dwg_to_pdf.input_resolver._is_reparse_point",
        lambda path: Path(path) == folder,
    )

    with pytest.raises(AppError) as raised:
        resolve_inputs([folder])

    assert raised.value.code == "E100"
    assert raised.value.path == folder
