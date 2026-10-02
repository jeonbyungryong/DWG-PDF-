from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.file_stability import require_stable


def test_require_stable_compares_size_and_mtime_twice(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "drawing.dwg"
    source.write_bytes(b"dwg")
    snapshots = iter((
        SimpleNamespace(st_size=3, st_mtime_ns=11),
        SimpleNamespace(st_size=3, st_mtime_ns=11),
    ))
    monkeypatch.setattr("dwg_to_pdf.file_stability._stat", lambda path: next(snapshots))
    monkeypatch.setattr("dwg_to_pdf.file_stability._sleep", lambda seconds: None)

    require_stable(source, interval_sec=0)


def test_require_stable_holds_changed_or_unreadable_files_closed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "drawing.dwg"
    source.write_bytes(b"dwg")
    snapshots = iter((
        SimpleNamespace(st_size=3, st_mtime_ns=11),
        SimpleNamespace(st_size=4, st_mtime_ns=11),
    ))
    monkeypatch.setattr("dwg_to_pdf.file_stability._stat", lambda path: next(snapshots))
    monkeypatch.setattr("dwg_to_pdf.file_stability._sleep", lambda seconds: None)

    with pytest.raises(AppError) as raised:
        require_stable(source, interval_sec=0)

    assert raised.value.code == "E215"


def test_require_stable_wraps_sleep_boundary_failures(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "drawing.dwg"
    source.write_bytes(b"dwg")
    monkeypatch.setattr(
        "dwg_to_pdf.file_stability._sleep",
        lambda seconds: (_ for _ in ()).throw(OverflowError("too large")),
    )

    with pytest.raises(AppError) as raised:
        require_stable(source, interval_sec=1.0)

    assert raised.value.code == "E215"
