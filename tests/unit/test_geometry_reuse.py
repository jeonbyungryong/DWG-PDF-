"""Exercise real geometry readers against a counted external CAD boundary."""
from collections import Counter
from types import SimpleNamespace
import math

import pytest

from dwg_to_pdf.cad.com_document import ComDocument
from dwg_to_pdf.domain import Point, Rect
from dwg_to_pdf.errors import AppError


class Entity:
    def __init__(self, **values):
        self.values = values
        self.reads = Counter()

    def __getattr__(self, name):
        self.reads[name] += 1
        if name not in self.values:
            raise AttributeError(name)
        return self.values[name]


def line(handle="L", end=(4, 2, 0)):
    return Entity(ObjectName="AcDbLine", Handle=handle,
                  StartPoint=(1, 2, 0), EndPoint=end)


class Selection:
    def __init__(self, entities, owner):
        self.entities, self.owner = entities, owner
        self.Count = len(entities)

    def Select(self, mode, lower, upper, types, values):
        self.owner.queries.append((mode, tuple(lower.value), tuple(upper.value), tuple(values.value)))

    def Item(self, index):
        return self.entities[index]

    def Delete(self):
        self.owner.deletes += 1


class Selections:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.queries = []
        self.deletes = 0

    def Item(self, name):
        raise KeyError(name)

    def Add(self, name):
        return Selection(next(self.batches), self)


class Block:
    def __init__(self, entities):
        self.entities, self.Count, self.reads = entities, len(entities), 0

    def Item(self, index):
        self.reads += 1
        return self.entities[index]


class Blocks:
    def __init__(self, blocks):
        self.blocks, self.reads = blocks, Counter()

    def Item(self, name):
        self.reads[name] += 1
        return self.blocks[name]


def bounds(size):
    return Rect(Point(0, 0), Point(size, size))


def reference(handle="R", point=(0, 0), rotation=0, **extra):
    return dict(block_name="B", handle=handle, point=point, rotation=rotation,
                x_scale=1, y_scale=1, **extra)


def test_overlapping_candidates_reuse_properties_but_keep_each_server_selection():
    a, b = line(), line("B", (8, 2, 0))
    selections = Selections([[a], [a], [b]])
    doc = ComDocument(SimpleNamespace(SelectionSets=selections))
    doc.configure_extraction(False)
    first = doc.filtered_geometry_snapshots(bounds(10))
    first[0]["start"] = (999, 999)  # caller must not poison cached data
    second = doc.filtered_geometry_snapshots(bounds(20))
    third = doc.filtered_geometry_snapshots(bounds(30))
    assert second == [{"type": "LINE", "start": (1, 2), "end": (4, 2), "handle": "L"}]
    assert [s["handle"] for s in third] == ["B"]
    assert a.reads["StartPoint"] == a.reads["EndPoint"] == 1
    assert len(selections.queries) == selections.deletes == 3
    assert [q[2] for q in selections.queries] == [(10, 10, 0), (20, 20, 0), (30, 30, 0)]
    assert all(q[3] == ("LINE,LWPOLYLINE,INSERT",) for q in selections.queries)


def test_reached_block_reuse_keeps_instance_rotation_translation_and_identity():
    entity = line()
    block = Block([entity])
    blocks = Blocks({"B": block})
    doc = ComDocument(SimpleNamespace(Blocks=blocks))
    doc.configure_extraction(False)
    first = doc.nested_geometry_snapshots(reference("R1"), 4, 10)
    second = doc.nested_geometry_snapshots(reference("R2", (10, 20), math.pi / 2), 4, 10)
    assert first[0]["start"] == (1, 2)
    assert second[0]["start"] == pytest.approx((8, 21))
    assert second[0]["end"] == pytest.approx((8, 24))
    assert first[0]["instance_path"] == ("R1",)
    assert second[0]["instance_path"] == ("R2",)
    assert entity.reads["StartPoint"] == 1
    assert blocks.reads["B"] == block.reads == 1


def test_cached_block_still_charges_entity_budget():
    doc = ComDocument(SimpleNamespace(Blocks=Blocks({"B": Block([line(), line("L2")])})))
    doc.configure_extraction(False)
    assert len(doc.nested_geometry_snapshots(reference(), 4, 10)) == 2
    with pytest.raises(AppError, match="entity"):
        doc.nested_geometry_snapshots(reference("R2"), 4, 1)


def test_analysis_reset_and_different_document_do_not_reuse_stale_properties():
    entity = line()
    selections = Selections([[entity], [entity]])
    doc = ComDocument(SimpleNamespace(SelectionSets=selections))
    doc.configure_extraction(False)
    doc.filtered_geometry_snapshots(bounds(10))
    entity.values["EndPoint"] = (9, 2, 0)
    doc.configure_extraction(False)  # same setting, new analysis boundary
    assert doc.filtered_geometry_snapshots(bounds(10))[0]["end"] == (9, 2)
    other = ComDocument(SimpleNamespace(SelectionSets=Selections([[line(end=(7, 2, 0))]])))
    other.configure_extraction(False)
    assert other.filtered_geometry_snapshots(bounds(10))[0]["end"] == (7, 2)


def test_registration_without_conversion_opt_in_keeps_fresh_geometry_reads():
    entity = line()
    doc = ComDocument(SimpleNamespace(SelectionSets=Selections([[entity], [entity]])))
    doc.filtered_geometry_snapshots(bounds(10))
    entity.values["EndPoint"] = (9, 2, 0)
    assert doc.filtered_geometry_snapshots(bounds(20))[0]["end"] == (9, 2)
    assert entity.reads["StartPoint"] == 2


def test_cached_block_does_not_bypass_unsupported_instance_transform():
    doc = ComDocument(SimpleNamespace(Blocks=Blocks({"B": Block([line()])})))
    doc.configure_extraction(False)
    doc.nested_geometry_snapshots(reference(), 4, 10)
    bad = reference("BAD")
    bad["y_scale"] = 2
    with pytest.raises(AppError):
        doc.nested_geometry_snapshots(bad, 4, 10)


def test_failed_property_read_is_not_cached_as_success():
    entity = line(end=(math.nan, 2, 0))
    doc = ComDocument(SimpleNamespace(SelectionSets=Selections([[entity], [entity]])))
    doc.configure_extraction(False)
    with pytest.raises(AppError, match="non-finite"):
        doc.filtered_geometry_snapshots(bounds(10))
    entity.values["EndPoint"] = (4, 2, 0)
    assert doc.filtered_geometry_snapshots(bounds(20))[0]["end"] == (4, 2)
    assert entity.reads["EndPoint"] == 2


def test_cached_skipped_objects_still_consume_traversal_budget():
    unsupported = Entity(ObjectName="AcDbCircle")
    doc = ComDocument(SimpleNamespace(Blocks=Blocks({"B": Block([unsupported, line()])})))
    doc.configure_extraction(False)
    assert len(doc.nested_geometry_snapshots(reference(), 4, 10)) == 1
    with pytest.raises(AppError, match="entity"):
        doc.nested_geometry_snapshots(reference("R2"), 4, 1)


def test_empty_handles_do_not_merge_distinct_selected_entities():
    first, second = line(""), line("", (9, 2, 0))
    doc = ComDocument(SimpleNamespace(SelectionSets=Selections([[first], [second]])))
    doc.configure_extraction(False)
    assert doc.filtered_geometry_snapshots(bounds(10))[0]["end"] == (4, 2)
    assert doc.filtered_geometry_snapshots(bounds(20))[0]["end"] == (9, 2)


def test_entity_storage_cap_stops_reuse_without_dropping_geometry():
    initial = [line(str(i)) for i in range(5000)]
    overflow = line("OVERFLOW", (9, 2, 0))
    doc = ComDocument(SimpleNamespace(SelectionSets=Selections([initial, [overflow], [overflow]])))
    doc.configure_extraction(False)
    assert len(doc.filtered_geometry_snapshots(bounds(10))) == 5000
    assert doc.filtered_geometry_snapshots(bounds(20))[0]["end"] == (9, 2)
    assert doc.filtered_geometry_snapshots(bounds(30))[0]["end"] == (9, 2)
    assert overflow.reads["StartPoint"] == 2


def test_block_storage_cap_is_aggregate_not_per_definition():
    a = Block([line(f"A{i}") for i in range(2500)])
    b = Block([line(f"B{i}") for i in range(2501)])
    blocks = Blocks({"B": a, "SECOND": b})
    doc = ComDocument(SimpleNamespace(Blocks=blocks))
    doc.configure_extraction(False)
    assert len(doc.nested_geometry_snapshots(reference(), 4, 5000)) == 2500
    second = reference("R2")
    second["block_name"] = "SECOND"
    assert len(doc.nested_geometry_snapshots(second, 4, 5000)) == 2501
    assert len(doc.nested_geometry_snapshots(second, 4, 5000)) == 2501
    assert blocks.reads["SECOND"] == 2  # overflow still traversed, not retained


def test_empty_block_can_be_reused_without_inventing_geometry():
    blocks = Blocks({"B": Block([])})
    doc = ComDocument(SimpleNamespace(Blocks=blocks))
    doc.configure_extraction(False)
    assert doc.nested_geometry_snapshots(reference(), 4, 10) == []
    assert doc.nested_geometry_snapshots(reference("R2"), 4, 10) == []
    assert blocks.reads["B"] == 1


def test_cyclic_block_reuse_keeps_cycle_guard_and_instance_paths():
    cyclic = Entity(ObjectName="AcDbBlockReference", Handle="SELF", Name="B",
                    InsertionPoint=(0, 0, 0), Rotation=0,
                    XScaleFactor=1, YScaleFactor=1, HasAttributes=False)
    blocks = Blocks({"B": Block([cyclic, line()])})
    doc = ComDocument(SimpleNamespace(Blocks=blocks))
    doc.configure_extraction(False)
    assert len(doc.nested_geometry_snapshots(reference(), 1, 2)) == 1
    second = doc.nested_geometry_snapshots(reference("R2", (10, 20)), 1, 2)
    assert second[0]["start"] == (11, 22)
    assert second[0]["instance_path"] == ("R2",)
    assert blocks.reads["B"] == 1


def test_partial_block_failure_is_not_promoted_to_a_complete_cache():
    bad = line("BAD", (math.nan, 2, 0))
    block = Block([line(), bad])
    blocks = Blocks({"B": block})
    doc = ComDocument(SimpleNamespace(Blocks=blocks))
    doc.configure_extraction(False)
    with pytest.raises(AppError, match="non-finite"):
        doc.nested_geometry_snapshots(reference(), 4, 10)
    bad.values["EndPoint"] = (9, 2, 0)
    repaired = doc.nested_geometry_snapshots(reference("R2"), 4, 10)
    assert len(repaired) == 2 and repaired[1]["end"] == (9, 2)
    assert blocks.reads["B"] == 2
    assert bad.reads["EndPoint"] == 2
