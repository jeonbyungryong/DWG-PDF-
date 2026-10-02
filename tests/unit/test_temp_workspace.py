from __future__ import annotations

import os
from pathlib import Path

import pytest

from dwg_to_pdf import temp_workspace as workspace_module
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.temp_workspace import SourceWorkspace, publish_pdf, sha256


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "drawing.dwg"
    source.write_bytes(b"AC1032 source drawing")
    return source


def test_workspace_creates_isolated_copy_and_cleans_it(tmp_path: Path) -> None:
    source = _source(tmp_path)
    before = (sha256(source), source.stat().st_mtime_ns)
    with SourceWorkspace(source) as workspace:
        working_copy = workspace.authorized_copy()
        assert working_copy != source.resolve()
        assert working_copy.read_bytes() == source.read_bytes()
        root = working_copy.parent
        working_copy.write_bytes(b"changed temporary copy")
    assert not root.exists()
    assert (sha256(source), source.stat().st_mtime_ns) == before


def test_workspace_rejects_use_before_enter_and_after_exit(tmp_path: Path) -> None:
    workspace = SourceWorkspace(_source(tmp_path))
    with pytest.raises(AppError) as before:
        workspace.authorized_copy()
    assert before.value.code == "E400"
    with workspace:
        assert workspace.authorized_copy().exists()
    with pytest.raises(AppError) as after:
        workspace.authorized_copy()
    assert after.value.code == "E400"


@pytest.mark.parametrize("replacement", ["source", "outside"])
def test_workspace_rejects_original_or_outside_authorized_path(
    tmp_path: Path, replacement: str
) -> None:
    source = _source(tmp_path)
    outside = tmp_path / "outside.dwg"
    outside.write_bytes(b"outside")
    with SourceWorkspace(source) as workspace:
        workspace._copy = source if replacement == "source" else outside
        with pytest.raises(AppError) as raised:
            workspace.authorized_copy()
    assert raised.value.code == "E400"


def test_workspace_rejects_non_dwg_and_symlink(tmp_path: Path) -> None:
    text = tmp_path / "drawing.txt"
    text.write_text("x", encoding="utf-8")
    with pytest.raises(AppError) as wrong_suffix:
        SourceWorkspace(text)
    assert wrong_suffix.value.code == "E400"

    source = _source(tmp_path)
    link = tmp_path / "link.dwg"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(AppError) as symlink:
        SourceWorkspace(link)
    assert symlink.value.code == "E400"


def test_workspace_reports_source_hash_or_mtime_change_and_still_cleans(tmp_path: Path) -> None:
    source = _source(tmp_path)
    workspace = SourceWorkspace(source)
    with pytest.raises(AppError) as changed:
        with workspace:
            root = workspace.authorized_copy().parent
            source.write_bytes(b"source was modified")
    assert changed.value.code == "E400"
    assert not root.exists()


def test_workspace_reports_mtime_only_change(tmp_path: Path) -> None:
    source = _source(tmp_path)
    workspace = SourceWorkspace(source)
    with pytest.raises(AppError) as changed:
        with workspace:
            before = source.stat().st_mtime_ns
            os.utime(source, ns=(before + 1_000_000, before + 1_000_000))
    assert changed.value.code == "E400"


def test_workspace_preserves_body_exception_when_source_is_unchanged(tmp_path: Path) -> None:
    source = _source(tmp_path)
    with pytest.raises(RuntimeError, match="body failed"):
        with SourceWorkspace(source):
            raise RuntimeError("body failed")


def test_workspace_retries_cleanup_without_hiding_first_failures(tmp_path: Path, monkeypatch) -> None:
    source = _source(tmp_path)
    calls: list[Path] = []
    real_rmtree = __import__("shutil").rmtree

    def flaky(path: Path) -> None:
        calls.append(Path(path))
        if len(calls) < 3:
            raise PermissionError("temporarily locked")
        real_rmtree(path)

    monkeypatch.setattr("dwg_to_pdf.temp_workspace._remove_tree", flaky, raising=False)
    monkeypatch.setattr("dwg_to_pdf.temp_workspace._sleep", lambda seconds: None, raising=False)
    with SourceWorkspace(source) as workspace:
        temp_dir = workspace.authorized_copy().parent

    assert len(calls) == 3
    assert not temp_dir.exists()


def test_workspace_cleanup_failure_is_stable_and_preserves_primary_detail(
    tmp_path: Path, monkeypatch
) -> None:
    source = _source(tmp_path)
    monkeypatch.setattr(
        "dwg_to_pdf.temp_workspace._remove_tree",
        lambda path: (_ for _ in ()).throw(PermissionError("still locked")),
        raising=False,
    )
    monkeypatch.setattr("dwg_to_pdf.temp_workspace._sleep", lambda seconds: None, raising=False)
    primary = RuntimeError("detection failed")
    temp_root = tmp_path / "workspaces"
    temp_root.mkdir()

    with pytest.raises(AppError) as raised:
        with SourceWorkspace(source, temp_root=temp_root):
            raise primary

    assert raised.value.code == "E400"
    assert raised.value.__cause__ is primary
    assert any("detection failed" in note for note in getattr(raised.value, "__notes__", ()))


def test_workspace_exit_reports_body_cleanup_and_source_change_together(
    tmp_path: Path, monkeypatch
) -> None:
    source = _source(tmp_path)
    temp_root = tmp_path / "workspaces"
    temp_root.mkdir()
    checks: list[Path] = []
    real_verify = workspace_module._verify_source_identity

    def verify(*args):
        checks.append(Path(args[0]))
        return real_verify(*args)

    monkeypatch.setattr(workspace_module, "_verify_source_identity", verify)
    monkeypatch.setattr(
        workspace_module,
        "_remove_tree",
        lambda path: (_ for _ in ()).throw(PermissionError("still locked")),
    )
    monkeypatch.setattr(workspace_module, "_sleep", lambda seconds: None)
    primary = RuntimeError("body failed")

    with pytest.raises(AppError) as raised:
        with SourceWorkspace(source, temp_root=temp_root):
            source.write_bytes(b"source changed during body")
            raise primary

    notes = getattr(raised.value, "__notes__", ())
    assert checks == [source.resolve()]
    assert raised.value.code == "E400"
    assert "변경" in str(raised.value)
    assert raised.value.__cause__ is primary
    assert any("body failed" in note for note in notes)
    assert any("정리할 수 없습니다" in note and str(temp_root) in note for note in notes)
    assert any(temp_root.iterdir())


def test_workspace_exit_checks_unchanged_source_after_cleanup_failure(
    tmp_path: Path, monkeypatch
) -> None:
    source = _source(tmp_path)
    temp_root = tmp_path / "workspaces"
    temp_root.mkdir()
    checks: list[Path] = []
    real_verify = workspace_module._verify_source_identity

    def verify(*args):
        checks.append(Path(args[0]))
        return real_verify(*args)

    monkeypatch.setattr(workspace_module, "_verify_source_identity", verify)
    monkeypatch.setattr(
        workspace_module,
        "_remove_tree",
        lambda path: (_ for _ in ()).throw(PermissionError("still locked")),
    )
    monkeypatch.setattr(workspace_module, "_sleep", lambda seconds: None)

    with pytest.raises(AppError) as raised:
        with SourceWorkspace(source, temp_root=temp_root):
            pass

    assert checks == [source.resolve()]
    assert raised.value.code == "E400"
    assert "정리할 수 없습니다" in str(raised.value)
    assert "변경" not in str(raised.value)


def test_workspace_exit_reports_source_change_after_successful_cleanup(
    tmp_path: Path, monkeypatch
) -> None:
    source = _source(tmp_path)
    checks: list[Path] = []
    real_verify = workspace_module._verify_source_identity

    def verify(*args):
        checks.append(Path(args[0]))
        return real_verify(*args)

    monkeypatch.setattr(workspace_module, "_verify_source_identity", verify)

    with pytest.raises(AppError) as raised:
        with SourceWorkspace(source) as workspace:
            temp_dir = workspace.authorized_copy().parent
            source.write_bytes(b"source changed during body")

    assert checks == [source.resolve()]
    assert raised.value.code == "E400"
    assert "변경" in str(raised.value)
    assert not temp_dir.exists()


@pytest.mark.parametrize("failure", ["temp_root", "stat", "mkdtemp", "copy"])
def test_workspace_filesystem_failures_are_wrapped(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    source = _source(tmp_path)
    if failure == "temp_root":
        monkeypatch.setattr(
            "dwg_to_pdf.temp_workspace._resolve_path",
            lambda path, strict: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )
        with pytest.raises(AppError) as raised:
            SourceWorkspace(source, temp_root=tmp_path)
    else:
        workspace = SourceWorkspace(source)
        if failure == "stat":
            monkeypatch.setattr(
                "dwg_to_pdf.temp_workspace._path_stat",
                lambda path: (_ for _ in ()).throw(PermissionError("denied")),
                raising=False,
            )
        elif failure == "mkdtemp":
            monkeypatch.setattr("dwg_to_pdf.temp_workspace.tempfile.mkdtemp", lambda **kwargs: (_ for _ in ()).throw(PermissionError("denied")))
        else:
            monkeypatch.setattr("dwg_to_pdf.temp_workspace.shutil.copy2", lambda *args: (_ for _ in ()).throw(PermissionError("denied")))
        with pytest.raises(AppError) as raised:
            with workspace:
                pass
    assert raised.value.code == "E400"


def test_workspace_samefile_failure_is_wrapped(tmp_path: Path, monkeypatch) -> None:
    source = _source(tmp_path)
    monkeypatch.setattr(
        "dwg_to_pdf.temp_workspace._same_file",
        lambda first, second: (_ for _ in ()).throw(PermissionError("denied")),
        raising=False,
    )

    with pytest.raises(AppError) as raised:
        with SourceWorkspace(source):
            pass
    assert raised.value.code == "E400"


def test_workspace_reparse_stat_failure_is_wrapped(tmp_path: Path, monkeypatch) -> None:
    source = _source(tmp_path)
    with SourceWorkspace(source) as workspace:
        monkeypatch.setattr(
            "dwg_to_pdf.temp_workspace._path_lstat",
            lambda path: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )
        with pytest.raises(AppError) as raised:
            workspace.authorized_copy()
    assert raised.value.code == "E400"


def test_publish_pdf_atomically_replaces_only_after_validation(tmp_path: Path, monkeypatch) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    temporary.write_bytes(b"new valid pdf")
    final.write_bytes(b"old valid pdf")
    calls: list[Path] = []
    monkeypatch.setattr(
        "dwg_to_pdf.temp_workspace.validate_pdf",
        lambda path: calls.append(path) or object(),
    )

    publish_pdf(temporary, final)

    assert calls == [temporary]
    assert final.read_bytes() == b"new valid pdf"
    assert not temporary.exists()


def test_publish_pdf_preserves_existing_output_when_validation_fails(tmp_path: Path, monkeypatch) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    temporary.write_bytes(b"bad")
    final.write_bytes(b"old valid pdf")

    def reject(path: Path) -> None:
        raise AppError("E420", "invalid PDF", path)

    monkeypatch.setattr("dwg_to_pdf.temp_workspace.validate_pdf", reject)
    with pytest.raises(AppError) as raised:
        publish_pdf(temporary, final)
    assert raised.value.code == "E420"
    assert final.read_bytes() == b"old valid pdf"
    assert not temporary.exists()


def test_publish_pdf_wraps_missing_temporary_and_preserves_existing_output(tmp_path: Path) -> None:
    temporary = tmp_path / "missing.pdf"
    final = tmp_path / "final.pdf"
    final.write_bytes(b"old valid pdf")

    with pytest.raises(AppError) as raised:
        publish_pdf(temporary, final)

    assert raised.value.code == "E420"
    assert final.read_bytes() == b"old valid pdf"


@pytest.mark.parametrize("failure", ["final_resolve", "mkdir", "replace"])
def test_publish_filesystem_failures_preserve_final_and_remove_temporary(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    temporary.write_bytes(b"valid")
    final.write_bytes(b"old valid pdf")
    monkeypatch.setattr("dwg_to_pdf.temp_workspace.validate_pdf", lambda path: object())
    if failure == "final_resolve":
        monkeypatch.setattr(
            "dwg_to_pdf.temp_workspace._resolve_path",
            lambda path, strict: (_ for _ in ()).throw(PermissionError("denied"))
            if Path(path) == final
            else Path(path).resolve(strict=strict),
            raising=False,
        )
    elif failure == "mkdir":
        monkeypatch.setattr(
            "dwg_to_pdf.temp_workspace._make_dir",
            lambda path: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )
    else:
        monkeypatch.setattr(
            "dwg_to_pdf.temp_workspace._replace_file",
            lambda *args: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )

    with pytest.raises(AppError) as raised:
        publish_pdf(temporary, final)
    assert raised.value.code in {"E420", "E421"}
    assert final.read_bytes() == b"old valid pdf"
    assert not temporary.exists()


def test_publish_cleanup_failure_preserves_final_and_primary_detail(
    tmp_path: Path, monkeypatch
) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    temporary.write_bytes(b"bad")
    final.write_bytes(b"old valid pdf")
    primary = AppError("E420", "invalid PDF", temporary)
    monkeypatch.setattr(
        "dwg_to_pdf.temp_workspace.validate_pdf",
        lambda path: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        "dwg_to_pdf.temp_workspace._remove_file",
        lambda path: (_ for _ in ()).throw(PermissionError("locked")),
        raising=False,
    )

    with pytest.raises(AppError) as raised:
        publish_pdf(temporary, final)
    assert raised.value.code == "E421"
    assert raised.value.__cause__ is primary
    assert final.read_bytes() == b"old valid pdf"


def test_publish_temporary_resolve_failure_removes_partial_and_preserves_final(
    tmp_path: Path, monkeypatch
) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    temporary.write_bytes(b"partial")
    final.write_bytes(b"old valid pdf")
    monkeypatch.setattr(
        "dwg_to_pdf.temp_workspace._resolve_path",
        lambda path, strict: (_ for _ in ()).throw(PermissionError("denied"))
        if Path(path) == temporary
        else Path(path).resolve(strict=strict),
    )

    with pytest.raises(AppError) as raised:
        publish_pdf(temporary, final)
    assert raised.value.code == "E420"
    assert not temporary.exists()
    assert final.read_bytes() == b"old valid pdf"
