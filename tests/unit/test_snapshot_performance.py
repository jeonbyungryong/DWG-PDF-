from collections import Counter
from types import SimpleNamespace

import pytest

from dwg_to_pdf.gstarcad.document import GstarDocument, _snapshot


class CountedEntity:
    """External CAD boundary with deterministic property-access accounting."""
    def __init__(self, **values):
        self.values = values
        self.reads = Counter()

    def __getattr__(self, name):
        self.reads[name] += 1
        if name not in self.values:
            raise AttributeError(name)
        return self.values[name]


def test_line_snapshot_fetches_each_coordinate_tuple_once():
    entity = CountedEntity(ObjectName="AcDbLine", StartPoint=(1, 2, 0), EndPoint=(3, 4, 0), Handle="L")
    result = _snapshot(entity)
    assert result["point"] == (1, 2)
    assert result["start"] == (1, 2)
    assert result["end"] == (3, 4)
    assert entity.reads["StartPoint"] == 1
    assert entity.reads["EndPoint"] == 1


def test_polyline_snapshot_fetches_coordinate_array_once():
    entity = CountedEntity(ObjectName="AcDbPolyline", Coordinates=(1, 2, 3, 4), Handle="P", Closed=False, Elevation=0, Normal=(0, 0, 1), GetBulge=lambda i: 0)
    result = _snapshot(entity)
    assert result["point"] == (1, 2)
    assert result["coordinates"] == (1, 2, 3, 4)
    assert entity.reads["Coordinates"] == 1


def test_insert_name_is_read_once_with_effective_name_present():
    entity = CountedEntity(ObjectName="AcDbBlockReference", Name="*U1", EffectiveName="TITLE", InsertionPoint=(5, 6, 0), Handle="I", Rotation=0, XScaleFactor=1, YScaleFactor=1, HasAttributes=False)
    result = _snapshot(entity)
    assert result["block_name"] == "*U1"
    assert result["effective_name"] == "TITLE"
    assert entity.reads["Name"] == 1


@pytest.mark.parametrize("method", ["nested_text_snapshots", "nested_geometry_snapshots"])
def test_nested_snapshot_reuses_the_already_read_entity_kind(method):
    entity = CountedEntity(ObjectName="AcDbLine", StartPoint=(1, 2, 0), EndPoint=(3, 4, 0), Handle="L")
    block = SimpleNamespace(Count=1, Item=lambda i: entity)
    document = GstarDocument(SimpleNamespace(Blocks=SimpleNamespace(Item=lambda name: block)))
    result = getattr(document, method)({"block_name": "B", "point": (0, 0), "handle": "I"}, 4, 10)
    assert result[0]["handle"] == "L"
    assert entity.reads["ObjectName"] == 1
