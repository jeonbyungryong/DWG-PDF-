from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.com_session import GstarSession
from dwg_to_pdf.temp_workspace import SourceWorkspace


@pytest.mark.parametrize("content", [b"", b"dwg", b"synthetic invalid DWG", b"%PDF-1.7", b"AC10xx"])
def test_non_dwg_working_copy_is_rejected_before_cad_open(tmp_path: Path, content: bytes):
    source = tmp_path / "drawing.dwg"
    source.write_bytes(content)
    session = GstarSession("unused")
    session._owns_app = True
    session.app = SimpleNamespace(Documents=SimpleNamespace(
        Open=lambda *args: pytest.fail("non-DWG contents must not reach blocking CAD Open")
    ))
    with SourceWorkspace(source) as workspace:
        with pytest.raises(AppError) as raised:
            with session.working_document(workspace):
                pass
    assert raised.value.code == "E203"
    assert source.read_bytes() == content
    assert session.document is None


@pytest.mark.parametrize("signature", [b"AC1009", b"AC1027", b"AC1032", b"AC9999"])
def test_dwg_signature_does_not_replace_cad_version_validation(tmp_path: Path, signature: bytes):
    source = tmp_path / "drawing.dwg"
    source.write_bytes(signature + b"fixture")
    opened = []
    closed = []
    def open_copy(path, readonly):
        opened.append((path, readonly))
        return SimpleNamespace(FullName=path, ReadOnly=False, Close=lambda save: closed.append(save))
    session = GstarSession("unused")
    session._owns_app = True
    session.app = SimpleNamespace(Documents=SimpleNamespace(Open=open_copy))
    invalid = tmp_path / "invalid.dwg"
    invalid.write_bytes(b"not DWG")
    with SourceWorkspace(invalid) as workspace:
        with pytest.raises(AppError):
            with session.working_document(workspace):
                pass
    assert session.is_usable and not opened
    with SourceWorkspace(source) as workspace:
        with session.working_document(workspace):
            assert opened == [(str(workspace.authorized_copy()), False)]
    assert closed == [False]
    assert source.read_bytes() == signature + b"fixture"


def test_unreadable_signature_is_file_failure_without_cad_open(tmp_path, monkeypatch):
    source = tmp_path / "drawing.dwg"
    source.write_bytes(b"AC1032fixture")
    session = GstarSession("unused")
    session._owns_app = True
    session.app = SimpleNamespace(Documents=SimpleNamespace(
        Open=lambda *args: pytest.fail("unreadable file must not reach CAD")
    ))
    original_open = Path.open
    with SourceWorkspace(source) as workspace:
        working_copy = workspace.authorized_copy()
        def denied(path, *args, **kwargs):
            if path == working_copy:
                raise PermissionError("deliberate unreadable signature")
            return original_open(path, *args, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", denied)
            with pytest.raises(AppError) as raised:
                with session.working_document(workspace):
                    pass
    assert raised.value.code == "E203"
    assert isinstance(raised.value.__cause__, PermissionError)
    assert session.document is None
