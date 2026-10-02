"""Generate opt-in regression DWGs from authorized template copies only."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pythoncom
from win32com.client import VARIANT
from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.gstarcad.template_detector import DetectionLimits, _bounded_text_and_insert_snapshots
from dwg_to_pdf.temp_workspace import SourceWorkspace, sha256


def point(x, y):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (x, y, 0.0))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output.resolve()
    if output == source.parent or output in source.parents:
        raise ValueError("fixture output must be separate from source directory")
    output.mkdir(parents=True, exist_ok=True)
    cases = [("shift", 0, None), ("rotate90", 90, None), ("rotate180", 180, None), ("rotate270", 270, None), ("blank", 0, ""), ("na", 0, "N/A"), ("nonuniform", 0, None)]
    if any((output / (name + ".DWG")).exists() for name, _, _ in cases):
        raise ValueError("refusing to overwrite existing fixture DWGs")
    identity = lambda: (sha256(source), source.stat().st_mtime_ns)
    before = identity()
    pids_before = _gstar_pids()
    rows = []
    with GstarSession("GStarCAD.Application.26") as session:
        owned = session.owned_pid
        with SourceWorkspace(source) as workspace:
            with session.working_document(workspace) as doc:
                snapshots = _bounded_text_and_insert_snapshots(doc, DetectionLimits(64, 5000))
                values = [x for x in snapshots if str(x.get("text", "")).strip() == "1:1"]
                labels = [x for x in snapshots if str(x.get("text", "")).strip().casefold() == "scale"]
                if len(values) != 1 or len(labels) != 1 or not labels[0].get("instance_path"):
                    raise ValueError("expected one nested Scale label and one 1:1 value")
                value_handle = str(values[0]["handle"])
                title_handle = str(labels[0]["instance_path"][0])
        for name, rotation, text in cases:
            destination = output / (name + ".DWG")
            with SourceWorkspace(source) as workspace:
                with session.working_document(workspace) as doc:
                    raw = doc.raw
                    if text is not None:
                        raw.HandleToObject(value_handle).TextString = text
                    if name == "nonuniform":
                        raw.HandleToObject(title_handle).XScaleFactor = 2.0
                    if text is None and name != "nonuniform":
                        model = raw.ModelSpace
                        for index in range(int(model.Count)):
                            entity = model.Item(index)
                            if rotation:
                                entity.Rotate(point(0, 0), math.radians(rotation))
                            entity.Move(point(0, 0), point(1000, -500))
                        model = entity = None
                    raw.SaveAs(str(destination))
                    raw = None
            rows.append({"file": str(destination), "rotation": rotation, "state": "blank" if text == "" else "na" if text == "N/A" else "valid", "expected_error": "E303" if name == "nonuniform" else None, "translation": [1000, -500] if text is None and name != "nonuniform" else [0, 0]})
            print("CREATED=" + name, flush=True)
    after_pids = _gstar_pids()
    result = {"source": str(source), "source_unchanged": before == identity(), "user_pids_before": sorted(pids_before), "user_pids_after": sorted(after_pids), "owned_pid_closed": owned not in after_pids, "cases": rows}
    (output / "manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    assert result["source_unchanged"] and result["owned_pid_closed"] and pids_before <= after_pids


if __name__ == "__main__":
    main()
