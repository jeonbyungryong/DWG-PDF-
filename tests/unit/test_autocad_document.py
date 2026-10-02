import json
import pytest

from dwg_to_pdf.autocad.document import AutoCADDocument
from dwg_to_pdf.autocad import native_extract
from dwg_to_pdf.cad.bulk_snapshot import parse_snapshot, NativeExtractionUnavailable
from dwg_to_pdf.errors import AppError


def raw_text(value="Scale"):
    return parse_snapshot(json.dumps({"version": 1, "token": "n", "document": "C:/work.dwg", "complete": True,
        "entities": [{"ObjectName": "AcDbText", "Handle": "1", "TextString": value, "InsertionPoint": [1, 2, 0]}], "blocks": {}}), "n", "C:/work.dwg")


def test_com_and_native_snapshot_decisions_equal(monkeypatch):
    raw = raw_text()
    calls = []
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda *args: calls.append(1) or raw)
    off = AutoCADDocument(raw)
    on = AutoCADDocument(raw, _bulk_enabled=True)
    assert off.for_scale_detection().filtered_snapshots(("TEXT",)) == on.for_scale_detection().filtered_snapshots(("TEXT",))
    assert calls == [1]


def test_cache_does_not_cross_documents(monkeypatch):
    first, second = raw_text("1:1"), raw_text("2:1")
    calls = []
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda raw, *args: calls.append(raw) or raw)
    a, b = AutoCADDocument(first, _bulk_enabled=True), AutoCADDocument(second, _bulk_enabled=True)
    for document, expected in ((a, "1:1"), (a, "1:1"), (b, "2:1")):
        assert document.for_scale_detection().filtered_snapshots(("TEXT",))[0]["text"] == expected
    assert calls == [first, second]


def test_identified_complete_unavailable_falls_back_once(monkeypatch):
    calls = []
    def unavailable(*args):
        calls.append(1)
        raise NativeExtractionUnavailable("unsupported")
    monkeypatch.setattr(native_extract, "extract_snapshot", unavailable)
    document = AutoCADDocument(raw_text(), _bulk_enabled=True)
    for _ in range(2):
        assert document.for_scale_detection().filtered_snapshots(("TEXT",))[0]["text"] == "Scale"
    assert calls == [1]


def test_identity_failure_has_no_fallback(monkeypatch):
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda *args: (_ for _ in ()).throw(AppError("E303", "identity mismatch")))
    with pytest.raises(AppError, match="identity"):
        AutoCADDocument(raw_text(), _bulk_enabled=True).for_scale_detection()
