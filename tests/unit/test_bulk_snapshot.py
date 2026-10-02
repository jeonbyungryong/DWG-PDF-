import importlib
import importlib.util
import json

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.document import GstarDocument


def parse(payload, token="job", document="C:/work/part.dwg"):
    name = "dwg_to_pdf.gstarcad.bulk_snapshot"
    assert importlib.util.find_spec(name), "bulk snapshot reader has not been implemented"
    return importlib.import_module(name).parse_snapshot(json.dumps(payload), token, document)


def drawing(entities, blocks=None):
    return {"version": 1, "token": "job", "document": "C:/work/part.dwg",
            "entities": entities, "blocks": blocks or {}, "complete": True}


def test_send_command_that_returns_after_deadline_is_rejected(monkeypatch):
    from types import SimpleNamespace
    from dwg_to_pdf.gstarcad import bulk_snapshot
    ticks = iter((0., 31.))
    monkeypatch.setattr(bulk_snapshot.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(bulk_snapshot.Path, 'exists', lambda self: True)
    raw = SimpleNamespace(FullName='C:/part.dwg', Activate=lambda: None,
                          SendCommand=lambda command: None)
    with pytest.raises(AppError, match='timed out'):
        bulk_snapshot.extract_snapshot(raw)


def text(value, handle, point):
    return {"ObjectName": "AcDbText", "Handle": handle,
            "TextString": value, "InsertionPoint": point}


def test_bulk_data_preserves_empty_unicode_and_literal_command_like_text():
    raw = parse(drawing([text("", "1", [1, 2, 0]),
                         text('한글 "(command)"\\', "2", [3, 4, 0])]))
    snapshots = GstarDocument(raw).for_scale_detection().filtered_snapshots(("TEXT",))
    assert [(s["text"], s["point"], s["handle"]) for s in snapshots] == [
        ("", (1, 2), "1"), ('한글 "(command)"\\', (3, 4), "2")]


def test_bulk_data_keeps_instance_identity_and_parent_coordinate_transform():
    root = {"ObjectName": "AcDbBlockReference", "Handle": "R", "Name": "B",
            "InsertionPoint": [100, 200, 0], "Rotation": 1.5707963267948966,
            "XScaleFactor": 1, "YScaleFactor": 1, "HasAttributes": False}
    raw = parse(drawing([root], {"B": [text("Scale", "T", [2, 3, 0])]}))
    doc = GstarDocument(raw).for_scale_detection()
    ref = doc.filtered_snapshots(("INSERT",))[0]
    found = doc.nested_text_snapshots(ref, 4, 10)[0]
    assert found["point"] == pytest.approx((97, 202))
    assert found["instance_path"] == ("R",)


@pytest.mark.parametrize("field,value", [
    ("token", "old-job"), ("document", "C:/other/file.dwg"),
    ("complete", False), ("version", 9),
])
def test_bulk_reader_rejects_wrong_or_incomplete_response(field, value):
    payload = drawing([])
    payload[field] = value
    with pytest.raises(AppError):
        parse(payload)


def test_bulk_data_does_not_hide_geometry_or_property_read_failures():
    line = {"ObjectName": "AcDbLine", "Handle": "L",
            "StartPoint": [0, 0, 0], "EndPoint": {"error": "read failed"}}
    raw = parse(drawing([line]))
    with pytest.raises(AppError):
        GstarDocument(raw).for_scale_detection().filtered_snapshots(("LINE",))


def test_conversion_bulk_view_keeps_registration_raw_and_reuses_one_query(monkeypatch):
    from dwg_to_pdf.gstarcad import bulk_snapshot
    original = object()
    native = parse(drawing([text("Scale", "1", [1, 2, 0])]))
    calls = []
    def extract(raw, types=("TEXT", "MTEXT", "INSERT"), bounds=None):
        assert raw is original
        calls.append((types, bounds))
        return native
    monkeypatch.setattr(bulk_snapshot, "extract_snapshot", extract)
    doc = GstarDocument(original, _bulk_enabled=True)
    first = doc.for_scale_detection()
    second = doc.for_scale_detection()
    assert first.filtered_snapshots(("TEXT",))[0]["text"] == "Scale"
    assert second.filtered_snapshots(("TEXT",))[0]["point"] == (1, 2)
    assert doc.raw is original
    assert not doc._lightweight_text
    assert len(calls) == 1


def test_complete_native_failure_uses_com_but_identity_failure_does_not(monkeypatch):
    from dwg_to_pdf.gstarcad import bulk_snapshot
    original = object()
    def failed_export(raw, *args):
        return parse({**drawing([]), "error": "bulk entity budget exceeded"})
    monkeypatch.setattr(bulk_snapshot, "extract_snapshot", failed_export)
    doc = GstarDocument(original, _bulk_enabled=True)
    assert doc.for_scale_detection().raw is original
    assert not doc._bulk_enabled
    monkeypatch.setattr(bulk_snapshot, "extract_snapshot",
                        lambda *a: parse({**drawing([]), "token": "stale"}))
    with pytest.raises(AppError):
        GstarDocument(original, _bulk_enabled=True).for_scale_detection()


def test_bulk_selection_preserves_requested_types():
    raw = parse(drawing([text("Scale", "T", [1, 2, 0]),
                        {"ObjectName": "AcDbLine", "Handle": "L",
                         "StartPoint": [0, 0, 0], "EndPoint": [1, 1, 0]}]))
    found = GstarDocument(raw).for_scale_detection().filtered_snapshots(("TEXT",))
    assert [item["handle"] for item in found] == ["T"]
