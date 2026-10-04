import json
from types import SimpleNamespace

import pytest

from dwg_to_pdf.autocad import native_extract
from dwg_to_pdf.cad import bulk_snapshot
from dwg_to_pdf.errors import AppError


def test_korean_space_quote_path_roundtrip():
    path = 'C:/한글 폴더/도면 "표본".dwg'
    assert bulk_snapshot._lisp_string(path) == '"C:/한글 폴더/도면 \\"표본\\".dwg"'
    payload = json.dumps({"version": 1, "token": "n", "document": path, "complete": True, "entities": [], "blocks": {}})
    assert bulk_snapshot.parse_snapshot(payload, "n", path).Blocks.Count == 0
    for encoding in ("utf-8", "cp949"):
        assert native_extract.decode_payload("한글 Scale".encode(encoding), "cp949") == "한글 Scale"


def test_timeout_does_not_retry_and_security_settings_unchanged(monkeypatch):
    calls = []
    ticks = iter((0., 31.))
    monkeypatch.setattr(bulk_snapshot.time, "monotonic", lambda: next(ticks))
    raw = SimpleNamespace(FullName="C:/한글/part.dwg", Activate=lambda: calls.append("activate"), SendCommand=lambda command: calls.append(command))
    raw.GetVariable = lambda name: 0 if name == "SECURELOAD" else ""
    with pytest.raises(AppError, match="timed out"):
        native_extract.extract_snapshot(raw)
    assert len(calls) == 2
    assert "SECURELOAD" not in calls[1] and "TRUSTEDPATHS" not in calls[1]


@pytest.mark.parametrize("change", [{"token": "stale"}, {"document": "other"}, {"complete": False}])
def test_nonce_document_complete_and_size_limits(change):
    data = {"version": 1, "token": "n", "document": "doc", "complete": True, "entities": [], "blocks": {}, **change}
    with pytest.raises(AppError) as error:
        bulk_snapshot.parse_snapshot(json.dumps(data), "n", "doc")
    assert error.value.code == "E303"


def test_size_limit():
    with pytest.raises(AppError):
        bulk_snapshot.parse_snapshot(" " * (bulk_snapshot.MAX_RESPONSE_BYTES + 1), "n", "doc")


@pytest.mark.parametrize("policy", [1, 2, 3, True])
def test_untrusted_native_script_falls_back_without_loading(policy):
    raw = SimpleNamespace(FullName="doc", GetVariable=lambda name: policy if name == "SECURELOAD" else "",
        Activate=lambda: pytest.fail("untrusted native transport must not run"))
    with pytest.raises(bulk_snapshot.NativeExtractionUnavailable):
        native_extract.extract_snapshot(raw)


def test_unreadable_security_policy_falls_back_without_loading():
    def variable(name):
        raise RuntimeError("cannot read policy")
    with pytest.raises(bulk_snapshot.NativeExtractionUnavailable):
        native_extract.extract_snapshot(SimpleNamespace(FullName="doc", GetVariable=variable,
            Activate=lambda: pytest.fail("unreadable native policy must not load code")))


@pytest.mark.parametrize("recursive", [False, True])
def test_trusted_script_reaches_native_transport(monkeypatch, recursive):
    from pathlib import Path
    directory = Path(bulk_snapshot.__file__).parent
    trusted = str(directory.parent) + "\\..." if recursive else str(directory)
    raw = SimpleNamespace(GetVariable=lambda name: 1 if name == "SECURELOAD" else trusted)
    sentinel = object()
    monkeypatch.setattr(bulk_snapshot, "extract_snapshot", lambda *args, **kwargs: sentinel)
    assert native_extract.extract_snapshot(raw) is sentinel
