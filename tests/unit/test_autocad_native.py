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
