from __future__ import annotations

from pathlib import Path

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.security_guard import audit_source_tree


def _assert_e214(path: Path) -> None:
    with pytest.raises(AppError) as raised:
        audit_source_tree(path)
    assert raised.value.code == "E214"


@pytest.mark.parametrize("source", ["import requests", "from httpx.client import Client", "import urllib.request", "from socket import socket", "import aiohttp.web"])
def test_audit_source_tree_rejects_banned_direct_and_from_imports(tmp_path: Path, source: str) -> None:
    (tmp_path / "module.py").write_text(source, encoding="utf-8")

    _assert_e214(tmp_path)


def test_audit_source_tree_allows_banned_words_in_strings_and_comments(tmp_path: Path) -> None:
    (tmp_path / "safe.py").write_text('# import requests\nmessage = "urllib.request"\n', encoding="utf-8")

    assert audit_source_tree(tmp_path) == (tmp_path / "safe.py",)


@pytest.mark.parametrize("content", ["def broken(:\n", b"\xff"])
def test_audit_source_tree_normalizes_parse_and_utf8_read_errors(tmp_path: Path, content: str | bytes) -> None:
    path = tmp_path / "broken.py"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")

    _assert_e214(tmp_path)


def test_audit_source_tree_skips_symlink_outside_package_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-audit.py"
    outside.write_text("import requests", encoding="utf-8")
    link = tmp_path / "escape.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable in this environment")

    assert audit_source_tree(tmp_path) == ()


def test_audit_source_tree_fails_closed_when_directory_walk_reports_an_error(tmp_path: Path, monkeypatch) -> None:
    def failing_walk(_root, *, followlinks, onerror):
        assert followlinks is False
        onerror(PermissionError("simulated traversal denial"))
        return iter(())

    monkeypatch.setattr("dwg_to_pdf.security_guard.os.walk", failing_walk)

    _assert_e214(tmp_path)


def test_audit_source_tree_fails_closed_when_file_is_replaced_by_an_outside_symlink_before_read(tmp_path: Path, monkeypatch) -> None:
    inside = tmp_path / "safe.py"
    outside = tmp_path.parent / "outside-replaced.py"
    inside.write_text("SAFE = True\n", encoding="utf-8")
    outside.write_text("OUTSIDE = True\n", encoding="utf-8")
    original_open = Path.open

    def swap_before_open(path: Path, *args, **kwargs):
        if path == inside and not path.is_symlink():
            path.unlink()
            try:
                path.symlink_to(outside)
            except OSError:
                pytest.skip("symlink creation unavailable in this environment")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", swap_before_open)

    _assert_e214(tmp_path)


def test_audit_source_tree_uses_no_follow_open_when_platform_support_is_available(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "safe.py"
    source.write_text("SAFE = True\n", encoding="utf-8")
    no_follow = 0x40000000
    real_open = __import__("os").open
    seen_flags: list[int] = []

    def recording_open(path, flags):
        seen_flags.append(flags)
        return real_open(path, flags & ~no_follow)

    monkeypatch.setattr("dwg_to_pdf.security_guard.os.O_NOFOLLOW", no_follow, raising=False)
    monkeypatch.setattr("dwg_to_pdf.security_guard.os.open", recording_open)

    assert audit_source_tree(tmp_path) == (source,)
    assert seen_flags and seen_flags[0] & no_follow


def test_audit_source_tree_accepts_current_production_source() -> None:
    package_root = Path(__file__).parents[2] / "src" / "dwg_to_pdf"

    audited = audit_source_tree(package_root)

    assert audited
    assert audited == tuple(sorted(audited, key=lambda path: path.as_posix().casefold()))
