from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dwg_to_pdf.domain import Point, Rect
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.reference_registrar import extract_reference_snapshot, register_reference


def _snapshot() -> dict[str, object]:
    return {
        "frame": [[0.0, 0.0], [21000.0, 14850.0]],
        "scale_label_point": [19000.0, 1000.0],
        "scale_value_point": [19000.0, 800.0],
        "scale_value": "1:50",
        "reference_window": [[0.0, 0.0], [21000.0, 14850.0]],
        "position_tolerance": 2.0,
        "scale_value_tolerance": 2.0,
        "structural_signature": {
            "segments": [
                [[-19000.0, -1000.0], [2000.0, -1000.0]],
                [[2000.0, -1000.0], [2000.0, 13850.0]],
                [[-19000.0, 13850.0], [2000.0, 13850.0]],
                [[-19000.0, -1000.0], [-19000.0, 13850.0]],
                [[1000.0, -1000.0], [1000.0, 1500.0]],
            ],
            "frame_segment_count": 4,
            "title_segment_count": 1,
            "orientation_anchor": [1000.0, 1500.0],
        },
    }


def test_registration_persists_value_cell_geometry_and_structural_signature(tmp_path: Path) -> None:
    source = tmp_path / "TEMPLETE_1대50.DWG"
    source.write_bytes(b"reference")
    raw = register_reference(
        _snapshot(), source, hashlib.sha256(b"reference").hexdigest(), source_root=tmp_path
    )
    assert raw["scale"] == {"numerator": "1", "denominator": "50"}
    assert raw["scale_value_offset"] == [0.0, -200.0]
    assert raw["structural_signature"]["frame_segment_count"] == 4
    assert "target_saved_window" not in raw


@pytest.mark.parametrize("value", ["1:20", "", "N/A"])
def test_registration_rejects_filename_internal_scale_mismatch_or_missing(value: str, tmp_path: Path) -> None:
    source = tmp_path / "TEMPLETE_1대50.DWG"
    snap = _snapshot()
    snap["scale_value"] = value
    with pytest.raises(AppError) as raised:
        register_reference(snap, source, "A" * 64, source_root=tmp_path)
    assert raised.value.code in {"E303", "E305"}


def test_registration_rejects_wrong_reference_window_dimensions(tmp_path: Path) -> None:
    source = tmp_path / "TEMPLETE_1대50.DWG"
    snap = _snapshot()
    snap["reference_window"] = [[0.0, 0.0], [20900.0, 14850.0]]
    with pytest.raises(AppError) as raised:
        register_reference(snap, source, "A" * 64, source_root=tmp_path)
    assert raised.value.code == "E301"


class ReferenceDocument:
    def __init__(
        self,
        *,
        value_text="1:1",
        value_box=((376.0, 15.0), (382.0, 17.0)),
        value_point=(380.0, 16.0),
        value_cell=((375.0, 14.0), (395.0, 18.0)),
        title_height=45.0,
        label_path=("FRAME", "LABEL"),
        cell_path=("FRAME",),
        extras=(),
        extra_geometry=(),
    ) -> None:
        self.saved_window = ((0.0, 0.0), (420.0, 297.0))
        self.value_text = value_text
        self.value_box = value_box
        self.value_point = value_point
        self.value_cell = value_cell
        self.title_height = title_height
        self.label_path = label_path
        self.cell_path = cell_path
        self.extras = extras
        self.extra_geometry = extra_geometry

    def filtered_snapshots(self, types, bounds=None):
        assert types == ("TEXT", "MTEXT", "INSERT") and bounds is None
        return [
            {"type": "TEXT", "text": "Scale", "point": (380.0, 20.0), "bbox": ((379.0, 19.0), (391.0, 23.0)), "handle": "L", "instance_path": self.label_path},
            {"type": "TEXT", "text": self.value_text, "point": self.value_point, "bbox": self.value_box, "handle": "V"},
            *self.extras,
        ]

    def nested_text_snapshots(self, reference, *, budget):
        raise AssertionError("no blocks")

    def approved_reference_window(self):
        return self.saved_window

    def filtered_geometry_snapshots(self, bounds):
        assert bounds == Rect(Point(0, 0), Point(420, 297))
        (cell_left, cell_bottom), (cell_right, cell_top) = self.value_cell
        return [
            {"type": "LINE", "start": (0.0, 0.0), "end": (420.0, 0.0), "handle": "1"},
            {"type": "LINE", "start": (420.0, 0.0), "end": (420.0, 297.0), "handle": "2"},
            {"type": "LINE", "start": (420.0, 297.0), "end": (0.0, 297.0), "handle": "3"},
            {"type": "LINE", "start": (0.0, 297.0), "end": (0.0, 0.0), "handle": "4"},
            {"type": "LINE", "start": (350.0, 0.0), "end": (350.0, self.title_height), "handle": "5"},
            {"type": "LINE", "start": (410.0, 0.0), "end": (420.0, 0.0), "handle": "6"},
            {"type": "LINE", "start": (cell_left, cell_bottom), "end": (cell_right, cell_bottom), "handle": "C1", "instance_path": self.cell_path},
            {"type": "LINE", "start": (cell_left, cell_top), "end": (cell_right, cell_top), "handle": "C2", "instance_path": self.cell_path},
            {"type": "LINE", "start": (cell_left, cell_bottom), "end": (cell_left, 24.0), "handle": "C3", "instance_path": self.cell_path},
            {"type": "LINE", "start": (cell_right, cell_bottom), "end": (cell_right, 24.0), "handle": "C4", "instance_path": self.cell_path},
            *self.extra_geometry,
        ]


def test_extract_reference_snapshot_learns_window_scale_cell_and_structure() -> None:
    snapshot = extract_reference_snapshot(
        ReferenceDocument(), Path("TEMPLETE_1대1.DWG"), max_nested_blocks=8, max_nested_entities=100
    )
    assert snapshot["reference_window"] == [[0.0, 0.0], [420.0, 297.0]]
    assert snapshot["scale_value_cell"] == [[375.0, 14.0], [395.0, 18.0]]
    assert snapshot["scale_value_point"] == [380.0, 16.0]
    assert snapshot["scale_value_tolerance"] == 1.0
    assert snapshot["structural_signature"]["frame_segment_count"] == 4
    assert snapshot["structural_signature"]["title_segment_count"] == 5
    assert snapshot["structural_signature"]["orientation_anchor"] == [-30.0, 25.0]


def test_extract_ignores_remote_ratio_but_rejects_multiple_objects_in_learned_value_cell() -> None:
    remote = {"type": "TEXT", "text": "1:99", "point": (20.0, 250.0), "bbox": ((19, 249), (30, 253)), "handle": "R"}
    snapshot = extract_reference_snapshot(
        ReferenceDocument(extras=(remote,)), Path("TEMPLETE_1대1.DWG"),
        max_nested_blocks=8, max_nested_entities=100,
    )
    assert snapshot["scale_value"] == "1:1"

    duplicate = {"type": "MTEXT", "text": "1:2", "point": (390.0, 16.0), "bbox": ((386, 15), (392, 17)), "handle": "D"}
    with pytest.raises(AppError) as raised:
        extract_reference_snapshot(
            ReferenceDocument(extras=(duplicate,)), Path("TEMPLETE_1대1.DWG"),
            max_nested_blocks=8, max_nested_entities=100,
        )
    assert raised.value.code == "E304"


def test_extract_rejects_zero_valid_ratio_objects_inside_measured_value_cell() -> None:
    remote = {"type": "TEXT", "text": "1:1", "point": (20.0, 250.0), "bbox": ((19, 249), (30, 253)), "handle": "R"}
    with pytest.raises(AppError) as raised:
        extract_reference_snapshot(
            ReferenceDocument(value_text="-", extras=(remote,)), Path("TEMPLETE_1대1.DWG"),
            max_nested_blocks=8, max_nested_entities=100,
        )
    assert raised.value.code == "E303"


def test_cell_boundaries_ignore_geometry_from_a_different_block_instance() -> None:
    part_line = {
        "type": "LINE", "start": (300.0, 17.0), "end": (410.0, 17.0),
        "handle": "PART", "instance_path": ("PART",),
    }
    snapshot = extract_reference_snapshot(
        ReferenceDocument(extra_geometry=(part_line,)), Path("TEMPLETE_1대1.DWG"),
        max_nested_blocks=8, max_nested_entities=100,
    )
    assert snapshot["scale_value_cell"] == [[375.0, 14.0], [395.0, 18.0]]


def test_top_level_label_uses_only_top_level_grid_not_closer_nested_block_geometry() -> None:
    foreign_grid = (
        {"type": "LINE", "start": (379.0, 19.0), "end": (390.0, 19.0), "handle": "F1", "instance_path": ("FOREIGN",)},
        {"type": "LINE", "start": (379.0, 17.0), "end": (390.0, 17.0), "handle": "F2", "instance_path": ("FOREIGN",)},
        {"type": "LINE", "start": (379.0, 16.0), "end": (379.0, 21.0), "handle": "F3", "instance_path": ("FOREIGN",)},
        {"type": "LINE", "start": (390.0, 16.0), "end": (390.0, 21.0), "handle": "F4", "instance_path": ("FOREIGN",)},
    )
    snapshot = extract_reference_snapshot(
        ReferenceDocument(label_path=(), cell_path=(), extra_geometry=foreign_grid),
        Path("TEMPLETE_1대1.DWG"),
        max_nested_blocks=8,
        max_nested_entities=100,
    )
    assert snapshot["scale_value_cell"] == [[375.0, 14.0], [395.0, 18.0]]


def test_tolerances_are_learned_from_measured_text_and_structure_geometry() -> None:
    small = extract_reference_snapshot(
        ReferenceDocument(value_box=((378, 15), (382, 17)), title_height=5),
        Path("TEMPLETE_1대1.DWG"), max_nested_blocks=8, max_nested_entities=100,
    )
    large = extract_reference_snapshot(
        ReferenceDocument(value_box=((376, 15), (384, 18)), title_height=60),
        Path("TEMPLETE_1대1.DWG"), max_nested_blocks=8, max_nested_entities=100,
    )
    assert small["scale_value_tolerance"] != large["scale_value_tolerance"]
    assert small["position_tolerance"] != large["position_tolerance"]
