from __future__ import annotations

from dataclasses import dataclass, replace
import math
from types import SimpleNamespace

import pytest
import pythoncom

from decimal import Decimal
from pathlib import Path

from dwg_to_pdf.domain import Point, Rect, ScaleRatio, TemplateProfile
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.document import GstarDocument
from dwg_to_pdf.gstarcad.template_detector import (
    DetectionLimits,
    detect_scale_candidates,
    detect_scale_cell,
    verify_rotation,
)
from dwg_to_pdf.templates.structural_signature import StructuralSignature


def _profile(
    *,
    offset: Point = Point(0.0, -10.0),
    tolerance: float = 0.25,
    scale: ScaleRatio = ScaleRatio(Decimal("1"), Decimal("50")),
) -> TemplateProfile:
    return TemplateProfile(
        profile_id="test-profile",
        scale=scale,
        source_path=Path("reference.dwg"),
        source_sha256="A" * 64,
        approved=True,
        frame=Rect(Point(0, 0), Point(100, 50)),
        scale_anchor=Point(20, 10),
        scale_value_offset=offset,
        scale_value_tolerance=tolerance,
        orientation_anchor=Point(90, 5),
        reference_window=Rect(Point(0, 0), Point(100, 50)),
        position_tolerance=1.0,
    )


class ScaleCellDocument:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def filtered_snapshots(self, types, bounds=None):
        assert types == ("TEXT", "MTEXT", "INSERT")
        assert bounds is None
        return list(self.snapshots)

    def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
        return []


def _cell_document(value_text: str | None, value_point=(100.0, 40.0)) -> ScaleCellDocument:
    items = [{"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"}]
    if value_text is not None:
        items.append({"type": "TEXT", "text": value_text, "point": value_point, "handle": "V"})
    return ScaleCellDocument(items)


@pytest.mark.parametrize(
    ("text", "expected_state"),
    [(None, "blank"), ("", "blank"), (" N/A ", "na"), ("n/a", "na")],
)
def test_scale_cell_preserves_blank_or_na_for_fallback(text, expected_state) -> None:
    cell = detect_scale_cell(_cell_document(text), DetectionLimits(64, 5000), (_profile(),))
    assert cell.state == expected_state
    assert cell.token is None


@pytest.mark.parametrize("token,state", [("1:50", "valid"), ("", "blank"), ("N/A", "na")])
def test_conversion_scale_detection_does_not_request_registration_bounds(token, state):
    def unused_bounds():
        pytest.fail("conversion must not request registration-only text bounds")
    label = _text("Scale", (100, 50, 0), "L")
    value = _text(token, (100, 40, 0), "V")
    label.GetBoundingBox = value.GetBoundingBox = unused_bounds
    selection = FakeSelection([label, value])
    doc = GstarDocument(SimpleNamespace(SelectionSets=FakeSelectionSets(selection)))
    cell = detect_scale_cell(doc, DetectionLimits(64, 5000), (_profile(),))
    assert cell.state == state
    assert selection.deleted


def test_default_snapshot_keeps_measured_bounds_for_registration():
    label = _text("Scale", (100, 50, 0), "L")
    label.GetBoundingBox = lambda: ((99, 49, 0), (104, 52, 0))
    selection = FakeSelection([label])
    doc = GstarDocument(SimpleNamespace(SelectionSets=FakeSelectionSets(selection)))
    assert doc.filtered_snapshots(("TEXT",))[0]["bbox"] == ((99, 49), (104, 52))


@pytest.mark.parametrize("token,error", [("ABC", "E305"), ("1:50", "E304")])
def test_lightweight_detection_keeps_invalid_and_duplicate_cell_text(token, error):
    label = _text("Scale", (100, 50, 0), "L")
    values = [_text(token, (100, 40, 0), "V")]
    if error == "E304":
        values.append(_text("", (100, 40, 0), "EMPTY"))
    selection = FakeSelection([label, *values])
    doc = GstarDocument(SimpleNamespace(SelectionSets=FakeSelectionSets(selection)))
    with pytest.raises(AppError) as raised:
        detect_scale_cell(doc, DetectionLimits(64, 5000), (_profile(),))
    assert raised.value.code == error


def test_lightweight_nested_detection_avoids_nontext_property_probe_but_validates_line():
    class Line:
        ObjectName = "AcDbLine"
        StartPoint = (1, 2, 0)
        EndPoint = (3, 4, 0)
        Handle = "LINE"
        @property
        def TextString(self):
            pytest.fail("LINE has no TextString; do not probe it")
    line = Line()
    blocks = BlockCollection({"B": IndexedCollection([line])})
    doc = GstarDocument(SimpleNamespace(Blocks=blocks)).for_scale_detection()
    reference = {"block_name": "B", "point": (0, 0), "handle": "R"}
    assert doc.nested_text_snapshots(reference, 4, 10)[0]["text"] == ""
    line.EndPoint = (math.nan, 4, 0)
    with pytest.raises(AppError, match="non-finite"):
        doc.nested_text_snapshots(reference, 4, 10)


def test_scale_cell_accepts_valid_ratio_only_at_learned_value_geometry() -> None:
    document = ScaleCellDocument([
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "TEXT", "text": "1:10", "point": (100.0, 40.0), "handle": "V"},
        {"type": "TEXT", "text": "1:99", "point": (100.0, 49.0), "handle": "NEAR"},
    ])
    cell = detect_scale_cell(document, DetectionLimits(64, 5000), (_profile(),))
    assert (cell.state, cell.token) == ("valid", "1:10")


def test_valid_ratio_uses_its_own_profile_cell_and_ignores_text_at_another_profile_cell() -> None:
    document = ScaleCellDocument([
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V"},
        {"type": "TEXT", "text": "DRAWING TITLE", "point": (120.0, 50.0), "handle": "T"},
    ])
    profiles = (
        _profile(scale=ScaleRatio(Decimal("1"), Decimal("50"))),
        _profile(offset=Point(20.0, 0.0), scale=ScaleRatio(Decimal("1"), Decimal("20"))),
    )
    cell = detect_scale_cell(document, DetectionLimits(64, 5000), profiles)
    assert (cell.state, cell.token) == ("valid", "1:50")


@pytest.mark.parametrize(
    ("offset", "value_point", "expected_rotation"),
    [
        (Point(0.0, -10.0), (100.0, 40.0), 0),
        (Point(0.0, -10.0), (110.0, 50.0), 90),
        (Point(0.0, -10.0), (100.0, 60.0), 180),
        (Point(0.0, -10.0), (90.0, 50.0), 270),
    ],
)
def test_scale_cell_finds_learned_value_position_under_four_rotations(
    offset, value_point, expected_rotation
) -> None:
    cell = detect_scale_cell(
        _cell_document("1:50", value_point), DetectionLimits(64, 5000), (_profile(offset=offset),)
    )
    assert cell.state == "valid"
    assert cell.rotation_hint == expected_rotation


@pytest.mark.parametrize("count", [0, 2])
def test_scale_cell_requires_exactly_one_label(count: int) -> None:
    labels = [
        {"type": "TEXT", "text": "Scale", "point": (float(i), 0.0), "handle": f"L{i}"}
        for i in range(count)
    ]
    with pytest.raises(AppError) as raised:
        detect_scale_cell(ScaleCellDocument(labels), DetectionLimits(64, 5000), (_profile(),))
    assert raised.value.code == "E303"


def test_scale_cell_rejects_multiple_objects_at_learned_value_position() -> None:
    document = ScaleCellDocument([
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V1"},
        {"type": "MTEXT", "text": "", "point": (100.0, 40.0), "handle": "V2"},
    ])
    with pytest.raises(AppError) as raised:
        detect_scale_cell(document, DetectionLimits(64, 5000), (_profile(),))
    assert raised.value.code == "E304"


def test_scale_cell_never_treats_insert_as_value_object() -> None:
    document = ScaleCellDocument([
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "INSERT", "text": "1:50", "point": (100.0, 40.0), "handle": "I"},
    ])
    cell = detect_scale_cell(document, DetectionLimits(64, 5000), (_profile(),))
    assert cell.state == "blank"


def test_repeated_block_definition_handles_remain_distinct_physical_labels() -> None:
    document = ScaleCellDocument([
        {"type": "TEXT", "text": "Scale", "point": (0.0, 0.0), "handle": "DEF", "instance_path": ("I1",)},
        {"type": "TEXT", "text": "Scale", "point": (100.0, 0.0), "handle": "DEF", "instance_path": ("I2",)},
    ])
    with pytest.raises(AppError) as raised:
        detect_scale_cell(document, DetectionLimits(64, 5000), (_profile(),))
    assert raised.value.code == "E303"


def test_scale_cell_rejects_invalid_non_na_text() -> None:
    with pytest.raises(AppError) as raised:
        detect_scale_cell(_cell_document("UNKNOWN"), DetectionLimits(64, 5000), (_profile(),))
    assert raised.value.code == "E305"


@pytest.mark.parametrize("token,state", [("", "blank"), ("N/A", "na")])
def test_missing_ratio_uses_structure_before_other_profile_value_regions(token, state):
    first = replace(_profile(), profile_id="chosen")
    other = replace(_profile(offset=Point(20, 0)), profile_id="other")
    items = [
        {"type": "TEXT", "text": "Scale", "point": (100, 50), "handle": "L"},
        {"type": "TEXT", "text": token, "point": (100, 40), "handle": "V"},
        {"type": "MTEXT", "text": "GENERAL NOTE", "point": (120, 50), "handle": "N"},
        {"type": "LINE", "text": "", "point": (100, 40), "handle": "G"},
    ]
    decision = SimpleNamespace(candidate=SimpleNamespace(profile_id="chosen", rotation=0))
    cell = detect_scale_cell(
        ScaleCellDocument(items), DetectionLimits(64, 5000), (first, other),
        fallback_matcher=lambda cell: decision,
    )
    assert cell.state == state
    assert cell.rotation_hint == 0


@pytest.mark.parametrize("token,extra,error", [
    ("INVALID", False, "E305"), ("N/A", True, "E304"),
])
def test_structure_does_not_silence_invalid_or_duplicate_value(token, extra, error):
    doc = _cell_document(token)
    if extra:
        doc.snapshots.append({"type": "TEXT", "text": "", "point": (100, 40), "handle": "V2"})
    decision = SimpleNamespace(candidate=SimpleNamespace(profile_id="test-profile", rotation=0))
    with pytest.raises(AppError) as raised:
        detect_scale_cell(doc, DetectionLimits(64, 5000), (_profile(),),
                          fallback_matcher=lambda cell: decision)
    assert raised.value.code == error


def test_valid_ratio_in_another_profiles_value_cell_is_rejected():
    first = _profile()
    second = replace(_profile(offset=Point(0, -20),
                     scale=ScaleRatio(Decimal('1'), Decimal('100'))), profile_id='other')
    decision = SimpleNamespace(candidate=SimpleNamespace(profile_id=first.profile_id, rotation=0))
    with pytest.raises(AppError) as raised:
        detect_scale_cell(_cell_document('1:100'), DetectionLimits(64, 5000),
                          (first, second), fallback_matcher=lambda cell: decision)
    assert raised.value.code == 'E305'


@pytest.mark.parametrize(
    "profile",
    [_profile(offset=Point(math.nan, 0.0)), _profile(tolerance=math.inf), _profile(tolerance=0.0)],
)
def test_scale_cell_rejects_invalid_learned_geometry(profile: TemplateProfile) -> None:
    with pytest.raises(AppError) as raised:
        detect_scale_cell(_cell_document("1:50"), DetectionLimits(64, 5000), (profile,))
    assert raised.value.code == "E308"


class ExplodingCollection:
    def __iter__(self):
        raise AssertionError("full collection enumeration is forbidden")


@dataclass
class FakeDocument:
    ModelSpace = ExplodingCollection()
    Blocks = ExplodingCollection()

    def filtered_snapshots(self, types, bounds=None):
        assert types == ("TEXT", "MTEXT", "INSERT")
        assert bounds is None
        return [
            {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "10"},
            {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "11"},
        ]

    def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
        raise AssertionError("there are no references to traverse")


def test_detector_uses_only_filtered_snapshots() -> None:
    found = detect_scale_candidates(FakeDocument(), DetectionLimits(64, 5000))
    assert found == [found[0]]
    assert found[0].token == "1:50"
    assert found[0].anchor == Point(100.0, 50.0)


def test_detector_pairs_nearest_ratio_without_assuming_global_direction() -> None:
    class RotatedDocument(FakeDocument):
        def filtered_snapshots(self, types, bounds=None):
            return [
                {"type": "TEXT", "text": "Scale", "point": (0.0, 0.0), "handle": "L"},
                {"type": "TEXT", "text": "1:10", "point": (-2.0, 0.0), "handle": "V"},
                {"type": "TEXT", "text": "1:50", "point": (20.0, 0.0), "handle": "FAR"},
            ]

    assert detect_scale_candidates(RotatedDocument(), DetectionLimits(2, 10))[0].token == "1:10"


def test_detector_includes_text_and_attributes_reached_from_filtered_insert() -> None:
    class NestedDocument(FakeDocument):
        def filtered_snapshots(self, types, bounds=None):
            return [{
                "type": "INSERT", "block_name": "*U1", "point": (5.0, 5.0), "handle": "I",
                "rotation": 0.0, "x_scale": 1.0, "y_scale": 1.0,
            }]

        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            assert reference["block_name"] == "*U1"
            return [
                {"type": "ATTRIB", "text": "Scale", "point": (5.0, 5.0), "handle": "A"},
                {"type": "MTEXT", "text": "1:75", "point": (5.0, 6.0), "handle": "T"},
            ]

    found = detect_scale_candidates(NestedDocument(), DetectionLimits(2, 10))
    assert [item.token for item in found] == ["1:75"]


def test_detector_rejects_nonfinite_snapshot_geometry() -> None:
    class BadDocument(FakeDocument):
        def filtered_snapshots(self, types, bounds=None):
            return [{"type": "TEXT", "text": "Scale", "point": (math.nan, 0.0), "handle": "L"}]

    with pytest.raises(AppError, match="non-finite") as raised:
        detect_scale_candidates(BadDocument(), DetectionLimits(2, 10))
    assert raised.value.code == "E303"


class FakeSelection:
    def __init__(self, entities):
        self.entities = entities
        self.calls = []
        self.deleted = False

    @property
    def Count(self):
        return len(self.entities)

    def Item(self, index):
        return self.entities[index]

    def Select(self, *args):
        self.calls.append(args)

    def Delete(self):
        self.deleted = True


class FakeSelectionSets:
    def __init__(self, selection):
        self.selection = selection

    def Item(self, name):
        raise RuntimeError("not present")

    def Add(self, name):
        assert name.startswith("DWG_TO_PDF_FILTERED_")
        return self.selection


def test_filtered_snapshots_use_marshaled_server_side_filter_and_cleanup(monkeypatch) -> None:
    entity = SimpleNamespace(
        ObjectName="AcDbText", TextString="Scale", InsertionPoint=(1.0, 2.0, 0.0), Handle="A"
    )
    selection = FakeSelection([entity])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    marshalled = []

    def fake_variant(vt, value):
        marshalled.append((vt, value))
        return (vt, value)

    monkeypatch.setattr("dwg_to_pdf.cad.com_document.VARIANT", fake_variant)
    document = GstarDocument(raw)
    snapshots = document.filtered_snapshots(
        ("TEXT", "MTEXT", "INSERT"), Rect(Point(0.0, 0.0), Point(3.0, 4.0))
    )

    assert snapshots[0]["text"] == "Scale"
    assert selection.deleted is True
    assert len(selection.calls) == 1
    assert selection.calls[0][0] == 1
    assert selection.calls[0][1:3] == (
        (pythoncom.VT_ARRAY | pythoncom.VT_R8, (0.0, 0.0, 0.0)),
        (pythoncom.VT_ARRAY | pythoncom.VT_R8, (3.0, 4.0, 0.0)),
    )
    assert marshalled[0][1] == (0,)
    assert marshalled[1][1] == ("TEXT,MTEXT,INSERT",)
    assert marshalled[2][1] == (0.0, 0.0, 0.0)
    assert marshalled[3][1] == (3.0, 4.0, 0.0)


def test_filtered_geometry_snapshots_returns_line_endpoints_from_bounded_selection(monkeypatch) -> None:
    entity = SimpleNamespace(
        ObjectName="AcDbLine", StartPoint=(1.0, 2.0, 0.0), EndPoint=(3.0, 4.0, 0.0), Handle="G"
    )
    selection = FakeSelection([entity])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    monkeypatch.setattr("dwg_to_pdf.cad.com_document.VARIANT", lambda vt, value: (vt, value))
    document = GstarDocument(raw)

    result = document.filtered_geometry_snapshots(Rect(Point(0, 0), Point(5, 5)))

    assert result == [{"type": "LINE", "start": (1.0, 2.0), "end": (3.0, 4.0), "handle": "G"}]
    assert selection.calls[0][0] == 1
    assert selection.deleted is True


@pytest.mark.parametrize(
    ("bulge", "elevation", "normal"),
    [(0.1, 0.0, (0.0, 0.0, 1.0)), (0.0, 2.0, (0.0, 0.0, 1.0)), (0.0, 0.0, (0.0, 1.0, 0.0))],
)
def test_structural_lwpolyline_rejects_bulge_elevation_or_nonplanar_normal(monkeypatch, bulge, elevation, normal) -> None:
    entity = SimpleNamespace(
        ObjectName="AcDbPolyline", Coordinates=(0.0, 0.0, 10.0, 0.0), Handle="P",
        Closed=False, Elevation=elevation, Normal=normal, GetBulge=lambda index: bulge,
    )
    selection = FakeSelection([entity])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    monkeypatch.setattr("dwg_to_pdf.cad.com_document.VARIANT", lambda vt, value: (vt, value))
    with pytest.raises(AppError) as raised:
        GstarDocument(raw).filtered_geometry_snapshots(Rect(Point(-1, -1), Point(11, 1)))
    assert raised.value.code == "E303"


@pytest.mark.parametrize("missing", ["Elevation", "Normal"])
def test_structural_lwpolyline_rejects_missing_planarity_property(monkeypatch, missing) -> None:
    values = {
        "ObjectName": "AcDbPolyline", "Coordinates": (0.0, 0.0, 10.0, 0.0),
        "Handle": "P", "Closed": False, "Elevation": 0.0, "Normal": (0.0, 0.0, 1.0),
        "GetBulge": lambda index: 0.0,
    }
    del values[missing]
    selection = FakeSelection([SimpleNamespace(**values)])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    monkeypatch.setattr("dwg_to_pdf.cad.com_document.VARIANT", lambda vt, value: (vt, value))
    with pytest.raises(AppError) as raised:
        GstarDocument(raw).filtered_geometry_snapshots(Rect(Point(-1, -1), Point(11, 1)))
    assert raised.value.code == "E303"


@pytest.mark.parametrize("unreadable", ["Elevation", "Normal"])
def test_structural_lwpolyline_rejects_unreadable_planarity_property(monkeypatch, unreadable) -> None:
    class UnreadablePolyline:
        ObjectName = "AcDbPolyline"
        Coordinates = (0.0, 0.0, 10.0, 0.0)
        Handle = "P"
        Closed = False

        @property
        def Elevation(self):
            if unreadable == "Elevation":
                raise RuntimeError("Elevation unavailable")
            return 0.0

        @property
        def Normal(self):
            if unreadable == "Normal":
                raise RuntimeError("Normal unavailable")
            return (0.0, 0.0, 1.0)

        def GetBulge(self, index):
            return 0.0

    selection = FakeSelection([UnreadablePolyline()])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    monkeypatch.setattr("dwg_to_pdf.cad.com_document.VARIANT", lambda vt, value: (vt, value))
    with pytest.raises(AppError) as raised:
        GstarDocument(raw).filtered_geometry_snapshots(Rect(Point(-1, -1), Point(11, 1)))
    assert raised.value.code == "E303"


def test_unbounded_filter_passes_empty_optional_points_instead_of_null(monkeypatch) -> None:
    selection = FakeSelection([])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    monkeypatch.setattr("dwg_to_pdf.cad.com_document.VARIANT", lambda vt, value: (vt, value))

    GstarDocument(raw).filtered_snapshots(("TEXT",))

    assert selection.calls[0][1] is pythoncom.Empty
    assert selection.calls[0][2] is pythoncom.Empty


def test_filtered_snapshots_delete_selection_when_entity_is_invalid() -> None:
    selection = FakeSelection([SimpleNamespace(ObjectName="AcDbText")])
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(selection))
    with pytest.raises(AppError, match="snapshot"):
        GstarDocument(raw).filtered_snapshots(("TEXT",))
    assert selection.deleted is True


class IndexedCollection:
    def __init__(self, items):
        self.items = items

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index]


class BlockCollection:
    def __init__(self, blocks):
        self.blocks = blocks

    def __iter__(self):
        raise AssertionError("full Blocks iteration is forbidden")

    def Item(self, name):
        return self.blocks[name]


def _text(text, point, handle):
    return SimpleNamespace(ObjectName="AcDbText", TextString=text, InsertionPoint=point, Handle=handle)


def _insert(name, point, handle, *, rotation=0.0, sx=1.0, sy=1.0, attributes=()):
    return SimpleNamespace(
        ObjectName="AcDbBlockReference",
        Name=name,
        EffectiveName="VISIBLE_NAME",
        InsertionPoint=point,
        Handle=handle,
        Rotation=rotation,
        XScaleFactor=sx,
        YScaleFactor=sy,
        HasAttributes=bool(attributes),
        GetAttributes=lambda: attributes,
    )


@pytest.mark.parametrize("lightweight", [False, True])
def test_nested_traversal_reaches_anonymous_definition_and_transforms_quarter_turn(lightweight) -> None:
    blocks = BlockCollection({"*U1": IndexedCollection([_text("1:25", (2.0, 0.0, 0.0), "T")])})
    raw = SimpleNamespace(Blocks=blocks)
    reference = {
        "type": "INSERT", "block_name": "*U1", "point": (10.0, 20.0), "handle": "I",
        "rotation": math.pi / 2, "x_scale": 1.0, "y_scale": 1.0,
    }
    document = GstarDocument(raw)
    if lightweight:
        document = document.for_scale_detection()
    snapshots = document.nested_text_snapshots(reference, 4, 10)
    assert snapshots[0]["point"] == pytest.approx((10.0, 22.0))
    assert snapshots[0]["text"] == "1:25"


def test_nested_geometry_traversal_transforms_reached_line_without_full_blocks_iteration() -> None:
    line = SimpleNamespace(
        ObjectName="AcDbLine", StartPoint=(0.0, 0.0, 0.0), EndPoint=(2.0, 0.0, 0.0), Handle="G"
    )
    blocks = BlockCollection({"B": IndexedCollection([line])})
    raw = SimpleNamespace(Blocks=blocks)
    reference = {
        "type": "INSERT", "block_name": "B", "point": (10.0, 20.0), "handle": "I",
        "rotation": math.pi / 2, "x_scale": 1.0, "y_scale": 1.0,
    }

    snapshots = GstarDocument(raw).nested_geometry_snapshots(reference, 4, 10)

    assert snapshots == [{
        "type": "LINE", "start": pytest.approx((10.0, 20.0)),
        "end": pytest.approx((10.0, 22.0)), "handle": "G", "instance_path": ("I",),
    }]


@pytest.mark.parametrize(
    ("sx", "sy", "rotation"),
    [(2.0, 1.0, 0.0), (2.0, 2.0, 0.0), (1.0, 1.0, math.pi / 4), (math.nan, math.nan, 0.0)],
)
def test_nested_traversal_rejects_unsupported_or_nonfinite_transform(sx, sy, rotation) -> None:
    raw = SimpleNamespace(Blocks=BlockCollection({"B": IndexedCollection([])}))
    reference = {
        "type": "INSERT", "block_name": "B", "point": (0.0, 0.0), "handle": "I",
        "rotation": rotation, "x_scale": sx, "y_scale": sy,
    }
    with pytest.raises(AppError, match="transform") as raised:
        GstarDocument(raw).nested_text_snapshots(reference, 4, 10)
    assert raised.value.code == "E303"


def test_detector_ignores_scaled_oblique_annotation_before_scale_traversal() -> None:
    oblique_marker = SimpleNamespace(ObjectName="AcDbPoint", Handle="M")

    class GasketDocument(GstarDocument):
        def filtered_snapshots(self, types, bounds=None):
            assert types == ("TEXT", "MTEXT", "INSERT") and bounds is None
            return [
                {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
                {"type": "TEXT", "text": "1:5", "point": (100.0, 40.0), "handle": "V"},
                {
                    "type": "INSERT", "block_name": "_Oblique", "point": (0.0, 0.0),
                    "handle": "C07", "rotation": math.pi / 2, "x_scale": 17.5,
                    "y_scale": 17.5, "has_attributes": False,
                },
            ]

    document = GasketDocument(
        SimpleNamespace(Blocks=BlockCollection({"_Oblique": IndexedCollection([oblique_marker])}))
    )

    cell = detect_scale_cell(
        document,
        DetectionLimits(4, 10),
        (_profile(scale=ScaleRatio(Decimal("1"), Decimal("5"))),),
    )

    assert (cell.state, cell.token) == ("valid", "1:5")


def test_scale_detection_ignores_scaled_insert_that_only_contains_linework() -> None:
    line = SimpleNamespace(
        ObjectName="AcDbLine", StartPoint=(0.0, 0.0, 0.0), EndPoint=(2.0, 0.0, 0.0), Handle="F"
    )

    class GasketDocument(GstarDocument):
        def filtered_snapshots(self, types, bounds=None):
            assert types == ("TEXT", "MTEXT", "INSERT") and bounds is None
            return [
                {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
                {"type": "TEXT", "text": "1:5", "point": (100.0, 40.0), "handle": "V"},
                {
                    "type": "INSERT", "block_name": "FRAME", "point": (0.0, 0.0),
                    "handle": "F1", "rotation": 0.0, "x_scale": 2.0,
                    "y_scale": 2.0, "has_attributes": False,
                },
            ]

    document = GasketDocument(SimpleNamespace(Blocks=BlockCollection({"FRAME": IndexedCollection([line])})))

    cell = detect_scale_cell(
        document,
        DetectionLimits(4, 10),
        (_profile(scale=ScaleRatio(Decimal("1"), Decimal("5"))),),
    )

    assert (cell.state, cell.token) == ("valid", "1:5")


_UNSUPPORTED_ROOT_TRANSFORMS = (
    pytest.param(2.0, 2.0, 0.0, id="uniform-scale"),
    pytest.param(2.0, 1.0, 0.0, id="nonuniform-scale"),
    pytest.param(-1.0, 1.0, 0.0, id="mirror"),
    pytest.param(1.0, 1.0, math.pi / 4, id="non-quarter-turn"),
)


def _detector_contributor(kind: str):
    if kind == "text":
        return _text("Scale", (0.0, 0.0, 0.0), "T")
    if kind == "attribute":
        return SimpleNamespace(
            ObjectName="AcDbAttributeDefinition", TextString="Scale",
            InsertionPoint=(0.0, 0.0, 0.0), Handle="A",
        )
    if kind == "frame":
        return SimpleNamespace(
            ObjectName="AcDbLine", StartPoint=(0.0, 0.0, 0.0), EndPoint=(2.0, 0.0, 0.0), Handle="F"
        )
    raise AssertionError(f"unexpected contributor kind: {kind}")


def _transformed_document(contributor, sx: float, sy: float, rotation: float) -> GstarDocument:
    class RoutedDocument(GstarDocument):
        def filtered_snapshots(self, types, bounds=None):
            reference = {
                "type": "INSERT", "block_name": "CONTRIBUTOR", "point": (0.0, 0.0),
                "handle": "I", "rotation": rotation, "x_scale": sx, "y_scale": sy,
                "has_attributes": False,
            }
            if types == ("TEXT", "MTEXT", "INSERT"):
                assert bounds is None
                return [reference]
            if types == ("LINE", "LWPOLYLINE", "INSERT"):
                assert bounds is not None
                return [reference]
            raise AssertionError(f"unexpected filtered types: {types}")

    return RoutedDocument(SimpleNamespace(Blocks=BlockCollection({"CONTRIBUTOR": IndexedCollection([contributor])})))


@pytest.mark.parametrize(("sx", "sy", "rotation"), _UNSUPPORTED_ROOT_TRANSFORMS)
@pytest.mark.parametrize("kind", ("text", "attribute"))
def test_detector_remains_fail_closed_for_relevant_unsupported_root_transforms(kind, sx, sy, rotation) -> None:
    document = _transformed_document(_detector_contributor(kind), sx, sy, rotation)

    with pytest.raises(AppError, match="transform") as raised:
        detect_scale_candidates(document, DetectionLimits(4, 10))

    assert raised.value.code == "E303"


@pytest.mark.parametrize(("sx", "sy", "rotation"), _UNSUPPORTED_ROOT_TRANSFORMS)
def test_geometry_scoring_ignores_unsupported_insert_linework_and_scores_no_false_structure(sx, sy, rotation) -> None:
    frame = _detector_contributor("frame")
    document = _transformed_document(frame, sx, sy, rotation)
    bounds = Rect(Point(0.0, 0.0), Point(10.0, 10.0))

    assert document.filtered_geometry_snapshots(bounds) == []

    signature = StructuralSignature(
        (
            (Point(0, 0), Point(1, 0)), (Point(1, 0), Point(1, 1)),
            (Point(1, 1), Point(0, 1)), (Point(0, 1), Point(0, 0)),
            (Point(0, 0), Point(0.5, 0.5)),
        ),
        4,
        1,
        Point(0.5, 0.5),
    )
    profile = replace(_profile(), structural_signature=signature)
    candidate = SimpleNamespace(
        frame=bounds,
        scale_candidate=SimpleNamespace(anchor=Point(0.0, 0.0)),
        rotation=0,
    )
    assert verify_rotation(document, profile, candidate) == 0.0


def test_text_detection_ignores_non_text_primitive_under_unsupported_transform() -> None:
    unknown = SimpleNamespace(ObjectName="AcDbCircle", Handle="C")
    document = _transformed_document(unknown, 17.5, 17.5, math.pi / 2)

    assert detect_scale_candidates(document, DetectionLimits(4, 10)) == []


def test_text_detection_ignores_unrelated_note_text_under_unsupported_transform() -> None:
    note = _text("3EA", (0.0, 0.0, 0.0), "N")
    document = _transformed_document(note, 2.0, 2.0, 0.0)

    assert detect_scale_candidates(document, DetectionLimits(4, 10)) == []


def test_geometry_snapshots_are_cached_for_the_same_bounds() -> None:
    class CountingDocument(GstarDocument):
        calls = 0

        def filtered_snapshots(self, types, bounds=None):
            assert types == ("LINE", "LWPOLYLINE", "INSERT")
            self.calls += 1
            return [{
                "type": "LINE", "start": (0.0, 0.0), "end": (1.0, 0.0),
                "point": (0.0, 0.0), "handle": "L",
            }]

    bounds = Rect(Point(0.0, 0.0), Point(10.0, 10.0))
    document = CountingDocument(SimpleNamespace())

    first = document.filtered_geometry_snapshots(bounds)
    second = document.filtered_geometry_snapshots(bounds)

    assert first == second
    assert document.calls == 1


@pytest.mark.parametrize("lightweight", [False, True])
def test_nested_traversal_skips_attribute_definitions_when_instance_has_attributes(lightweight) -> None:
    definition = SimpleNamespace(
        ObjectName="AcDbAttributeDefinition",
        TextString="Scale",
        InsertionPoint=(0.0, 0.0, 0.0),
        Handle="DEF",
    )
    raw = SimpleNamespace(Blocks=BlockCollection({"B": IndexedCollection([definition])}))
    reference = {
        "type": "INSERT", "block_name": "B", "point": (0.0, 0.0), "handle": "R",
        "rotation": 0.0, "x_scale": 1.0, "y_scale": 1.0, "has_attributes": True,
    }

    document = GstarDocument(raw)
    if lightweight:
        document = document.for_scale_detection()
    assert document.nested_text_snapshots(reference, 4, 10) == []


def test_detector_skips_line_only_roots_before_enforcing_nested_root_limit() -> None:
    class ManyLineOnlyRoots(ScaleCellDocument):
        def is_noncontributing_text_insert(self, reference, *, budget):
            return True

        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            raise AssertionError("line-only roots must not be traversed")

    snapshots = [
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V"},
    ] + [
        {"type": "INSERT", "block_name": f"B{i}", "point": (0.0, 0.0), "handle": f"I{i}"}
        for i in range(3)
    ]

    cell = detect_scale_cell(ManyLineOnlyRoots(snapshots), DetectionLimits(2, 10), (_profile(),))

    assert (cell.state, cell.token) == ("valid", "1:50")


def test_text_relevance_scan_has_entity_bound_independent_of_nested_block_limit() -> None:
    class ManyDistinctLineOnlyRoots(ScaleCellDocument):
        def is_noncontributing_text_insert(self, reference, *, budget):
            budget.visit_block()
            budget.visit_entity()
            return True

        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            raise AssertionError("line-only roots must not be traversed")

    snapshots = [
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V"},
    ] + [
        {"type": "INSERT", "block_name": f"B{i}", "point": (0.0, 0.0), "handle": f"I{i}"}
        for i in range(3)
    ]

    cell = detect_scale_cell(ManyDistinctLineOnlyRoots(snapshots), DetectionLimits(2, 10), (_profile(),))

    assert (cell.state, cell.token) == ("valid", "1:50")


def test_supported_roots_under_limit_keep_fast_path_without_definition_classification() -> None:
    class SupportedFastPath(ScaleCellDocument):
        def is_noncontributing_unsupported_insert(self, reference, *, budget):
            return False

        def is_noncontributing_text_insert(self, reference, *, budget):
            raise AssertionError("supported roots under the limit must not be classified")

    snapshots = [
        {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "L"},
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V"},
        {"type": "INSERT", "block_name": "NORMAL", "point": (0.0, 0.0), "handle": "I"},
    ]

    cell = detect_scale_cell(SupportedFastPath(snapshots), DetectionLimits(2, 10), (_profile(),))

    assert (cell.state, cell.token) == ("valid", "1:50")


def test_generated_center_marks_are_removed_before_root_limit_and_never_traversed() -> None:
    class GeneratedCenterMarks(ScaleCellDocument):
        def is_known_noncontributing_text_insert(self, reference):
            return str(reference.get("block_name", "")).startswith("SW_CENTERMARKSYMBOL_")

        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            if str(reference.get("block_name", "")).startswith("SW_CENTERMARKSYMBOL_"):
                raise AssertionError("known geometry-only center marks must not be traversed")
            budget.visit_block()
            budget.visit_entity()
            return [{
                "type": "TEXT", "text": "Scale", "point": (100.0, 50.0),
                "handle": "L", "instance_path": (reference["handle"],),
            }]

    snapshots = [
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V"},
        {"type": "INSERT", "block_name": "TITLE", "point": (0.0, 0.0), "handle": "T"},
    ] + [
        {
            "type": "INSERT", "block_name": f"SW_CENTERMARKSYMBOL_{index}",
            "point": (0.0, 0.0), "handle": f"C{index}",
        }
        for index in range(80)
    ]

    cell = detect_scale_cell(GeneratedCenterMarks(snapshots), DetectionLimits(2, 10), (_profile(),))

    assert (cell.state, cell.token, cell.rotation_hint) == ("valid", "1:50", 0)


def test_only_unattributed_solidworks_center_mark_is_known_noncontributing() -> None:
    document = GstarDocument(SimpleNamespace())

    assert document.is_known_noncontributing_text_insert({
        "block_name": "SW_CENTERMARKSYMBOL_75", "has_attributes": False,
    })
    assert not document.is_known_noncontributing_text_insert({
        "block_name": "SW_CENTERMARKSYMBOL_75", "has_attributes": True,
    })
    assert not document.is_known_noncontributing_text_insert({
        "block_name": "CUSTOM_CENTERMARK", "has_attributes": False,
    })


def test_generated_center_marks_do_not_consume_geometry_root_budget() -> None:
    class CenterMarkGeometry(GstarDocument):
        def filtered_snapshots(self, types, bounds=None):
            return [{
                "type": "LINE", "start": (0.0, 0.0), "end": (10.0, 0.0),
                "point": (0.0, 0.0), "handle": "FRAME",
            }] + [{
                "type": "INSERT", "block_name": f"SW_CENTERMARKSYMBOL_{index}",
                "effective_name": f"SW_CENTERMARKSYMBOL_{index}",
                "point": (0.0, 0.0), "handle": f"C{index}",
                "has_attributes": False, "rotation": 0.0, "x_scale": 1.0, "y_scale": 1.0,
            } for index in range(80)]

        def nested_geometry_snapshots(self, reference, *args, **kwargs):
            raise AssertionError("known center marks must not be traversed for frame scoring")

    document = CenterMarkGeometry(SimpleNamespace())
    bounds = Rect(Point(0.0, 0.0), Point(100.0, 100.0))

    assert document.filtered_geometry_snapshots(bounds, max_blocks=2, max_entities=10) == [{
        "type": "LINE", "start": (0.0, 0.0), "end": (10.0, 0.0), "handle": "FRAME",
    }]


def test_unique_top_level_ratio_prioritizes_nearby_scale_block_and_stops_after_label() -> None:
    seen = []

    class PrioritizedScaleBlock(ScaleCellDocument):
        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            seen.append(reference["block_name"])
            if reference["block_name"] != "TITLE":
                raise AssertionError("unrelated distant block must not be traversed after Scale is found")
            budget.visit_block()
            budget.visit_entity()
            return [{
                "type": "TEXT", "text": "Scale", "point": (100.0, 50.0),
                "handle": "L", "instance_path": (reference["handle"],),
            }]

    snapshots = [
        {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "V"},
        {"type": "INSERT", "block_name": "DISTANT", "point": (0.0, 0.0), "handle": "D"},
        {"type": "INSERT", "block_name": "TITLE", "point": (99.0, 50.0), "handle": "T"},
    ]

    cell = detect_scale_cell(PrioritizedScaleBlock(snapshots), DetectionLimits(4, 10), (_profile(),))

    assert seen == ["TITLE"]
    assert (cell.state, cell.token, cell.rotation_hint) == ("valid", "1:50", 0)


def test_detector_enforces_aggregate_nested_snapshot_limit() -> None:
    class TooManyNested(ScaleCellDocument):
        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            items = [
                {"type": "TEXT", "text": "x", "point": (0.0, 0.0), "handle": f"{reference['handle']}-{i}"}
                for i in range(6)
            ]
            for _ in items:
                budget.visit_entity()
            return items

    roots = [
        {"type": "INSERT", "block_name": f"B{i}", "point": (0.0, 0.0), "handle": f"I{i}"}
        for i in range(2)
    ]
    with pytest.raises(AppError, match="aggregate entity limit"):
        detect_scale_cell(TooManyNested(roots), DetectionLimits(2, 10), (_profile(),))


def test_detector_passes_one_shared_budget_to_every_root() -> None:
    seen = []
    class SharedBudgetDocument(ScaleCellDocument):
        def nested_text_snapshots(self, reference, max_blocks=None, max_entities=None, *, budget=None):
            seen.append(budget)
            budget.visit_block()
            budget.visit_entity()
            return []

    roots = [
        {"type": "INSERT", "block_name": f"B{i}", "point": (0.0, 0.0), "handle": f"I{i}"}
        for i in range(2)
    ]
    with pytest.raises(AppError, match="Scale label"):
        detect_scale_cell(SharedBudgetDocument(roots), DetectionLimits(2, 2), (_profile(),))
    assert len(seen) == 2 and seen[0] is seen[1]


@pytest.mark.parametrize("lightweight", [False, True])
def test_nested_traversal_is_cycle_guarded_and_bounded(lightweight) -> None:
    blocks = BlockCollection({"A": IndexedCollection([_insert("A", (1.0, 0.0, 0.0), "I")])})
    raw = SimpleNamespace(Blocks=blocks)
    reference = {
        "type": "INSERT", "block_name": "A", "point": (0.0, 0.0), "handle": "R",
        "rotation": 0.0, "x_scale": 1.0, "y_scale": 1.0,
    }
    document = GstarDocument(raw)
    if lightweight:
        document = document.for_scale_detection()
    assert document.nested_text_snapshots(reference, 2, 2) == []


@pytest.mark.parametrize("lightweight", [False, True])
def test_nested_traversal_enforces_entity_limit(lightweight) -> None:
    blocks = BlockCollection({"B": IndexedCollection([_text("Scale", (0, 0, 0), "1"), _text("1:1", (1, 0, 0), "2")])})
    raw = SimpleNamespace(Blocks=blocks)
    reference = {
        "type": "INSERT", "block_name": "B", "point": (0.0, 0.0), "handle": "R",
        "rotation": 0.0, "x_scale": 1.0, "y_scale": 1.0,
    }
    with pytest.raises(AppError, match="entity limit"):
        document = GstarDocument(raw)
        if lightweight:
            document = document.for_scale_detection()
        document.nested_text_snapshots(reference, 2, 1)


@pytest.mark.parametrize("lightweight", [False, True])
def test_nested_traversal_reads_attached_attribute_values_in_parent_coordinates(lightweight) -> None:
    attribute = SimpleNamespace(
        ObjectName="AcDbAttribute", TextString="1:125", InsertionPoint=(3.0, 0.0, 0.0), Handle="A"
    )
    nested = _insert("B", (2.0, 0.0, 0.0), "I", attributes=(attribute,))
    blocks = BlockCollection({"A": IndexedCollection([nested]), "B": IndexedCollection([])})
    raw = SimpleNamespace(Blocks=blocks)
    reference = {
        "type": "INSERT", "block_name": "A", "point": (10.0, 0.0), "handle": "R",
        "rotation": 0.0, "x_scale": 1.0, "y_scale": 1.0,
    }

    document = GstarDocument(raw)
    if lightweight:
        document = document.for_scale_detection()
    snapshots = document.nested_text_snapshots(reference, 4, 10)

    assert snapshots == [{
        "type": "ATTRIB", "text": "1:125", "point": (13.0, 0.0), "handle": "A",
        "instance_path": ("R", "I"),
    }]


@pytest.mark.parametrize("profile_path", sorted((Path(__file__).parents[2] / "template_profiles").glob("*.json")), ids=lambda p: p.stem)
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("state", ["valid", "blank", "na"])
def test_all_registered_scale_cells_survive_nested_rigid_transforms(profile_path, rotation, state):
    from dwg_to_pdf.templates.profile_store import load_profile
    profiles = tuple(load_profile(p) for p in sorted(profile_path.parent.glob("*.json")))
    profile = next(p for p in profiles if p.profile_id == load_profile(profile_path).profile_id)
    label = _text("Scale", (profile.scale_anchor.x, profile.scale_anchor.y, 0), "LABEL")
    token = f"{profile.scale.numerator}:{profile.scale.denominator}" if state == "valid" else "N/A" if state == "na" else ""
    value = _text(token, (profile.scale_anchor.x + profile.scale_value_offset.x, profile.scale_anchor.y + profile.scale_value_offset.y, 0), "VALUE")
    reference = _insert("TITLE", (1234, -567, 0), "ROOT", rotation=math.radians(rotation))
    raw = SimpleNamespace(SelectionSets=FakeSelectionSets(FakeSelection([reference])), Blocks=BlockCollection({"TITLE": IndexedCollection([label, value])}))
    cell = detect_scale_cell(GstarDocument(raw), DetectionLimits(64, 5000), profiles)
    assert cell.state == state
    assert cell.token == (token if state == "valid" else None)
    if state == "valid":
        assert cell.rotation_hint == rotation
