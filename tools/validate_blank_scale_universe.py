"""Opt-in actual CAD regression across the 13 approved blank/N/A profiles."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pythoncom
from win32com.client import VARIANT
from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.gstarcad.template_detector import _bounded_text_and_insert_snapshots, DetectionLimits
from dwg_to_pdf.pdf_validator import validate_pdf
from dwg_to_pdf.templates.profile_store import ProfileStore
from dwg_to_pdf.templates.scale_label import parse_internal_scale
from dwg_to_pdf.temp_workspace import SourceWorkspace, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists():
        raise ValueError("use a new validation output directory")
    output.mkdir(parents=True)
    store = ProfileStore(root / "template_profiles", source_root=args.source_root)
    store.load_all()
    profiles = store.all()
    service = ConversionService(load_config(root / "config.toml"), store)
    identity = lambda p: (sha256(p), p.stat().st_mtime_ns)
    before = {str(p.source_path): identity(p.source_path) for p in profiles}
    pids = _gstar_pids()
    rows = []
    owned = None
    start = time.perf_counter()
    try:
        with GstarSession("GStarCAD.Application.26") as session:
            owned = session.owned_pid
            for profile in profiles:
                cases = [("", 0), ("N/A", 0)]
                if str(profile.scale.numerator) + ":" + str(profile.scale.denominator) in ("1:50", "100:1"):
                    cases += [("", 90), ("N/A", 270)]
                for value, angle in cases:
                    destination = output / f"case_{len(rows)+1:03d}.DWG"
                    row = {"input": destination.name, "expected_scale": asdict(profile.scale),
                           "state": "blank" if not value else "na", "rotation": angle}
                    rows.append(row)
                    t = time.perf_counter()
                    try:
                        with SourceWorkspace(profile.source_path) as workspace:
                            with session.working_document(workspace) as doc:
                                snapshots = _bounded_text_and_insert_snapshots(doc, DetectionLimits(64, 5000))
                                values = []
                                for item in snapshots:
                                    try:
                                        if parse_internal_scale(str(item.get("text", ""))) == profile.scale:
                                            values.append(item)
                                    except Exception:
                                        pass
                                if len(values) != 1:
                                    raise ValueError("expected one template scale value")
                                doc.raw.HandleToObject(values[0]["handle"]).TextString = value
                                if angle:
                                    model = doc.raw.ModelSpace
                                    origin = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (0., 0., 0.))
                                    for i in range(int(model.Count)):
                                        model.Item(i).Rotate(origin, math.radians(angle))
                                doc.raw.SaveAs(str(destination))
                        row["generation_seconds"] = time.perf_counter() - t
                        t = time.perf_counter()
                        outcome = service.convert_in_session(session, destination, output, "overwrite")
                        row["seconds"] = time.perf_counter() - t
                        row["outcome"] = asdict(outcome)
                        row["pdf"] = asdict(validate_pdf(outcome.frames[0].output))
                        row["correct"] = outcome.frames[0].scale == profile.scale and outcome.frames[0].rotation == angle
                    except Exception as exc:
                        row["error"] = str(exc)
                        row["cause"] = str(exc.__cause__)
                    print(json.dumps(row, default=str), flush=True)
    finally:
        after_pids = _gstar_pids()
        result = {"rows": rows, "seconds": time.perf_counter()-start,
                  "originals_unchanged": before == {str(p.source_path): identity(p.source_path) for p in profiles},
                  "owned_closed": owned not in after_pids,
                  "user_pids_preserved": pids <= after_pids,
                  "pids_before": sorted(pids), "pids_after": sorted(after_pids)}
        (output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return int(not all(r.get("correct", False) for r in rows) or not result["originals_unchanged"] or not result["owned_closed"] or not result["user_pids_preserved"])


if __name__ == "__main__":
    raise SystemExit(main())
