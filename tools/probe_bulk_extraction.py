"""Opt-in read-only real CAD comparison of COM and native extraction."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dwg_to_pdf.gstarcad import bulk_snapshot
from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.gstarcad.document import GstarDocument
from dwg_to_pdf.gstarcad.template_detector import detect_scale_cell, DetectionLimits
from dwg_to_pdf.templates.profile_store import ProfileStore
from dwg_to_pdf.temp_workspace import SourceWorkspace, sha256


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--result", type=Path, required=True)
    p.add_argument("--native-only", action="store_true")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    store = ProfileStore(root / "template_profiles", source_root=args.source_root)
    store.load_all()
    source = args.source.resolve(strict=True)
    before = (sha256(source), source.stat().st_mtime_ns)
    pids = _gstar_pids()
    result = {}
    original_parse = bulk_snapshot.parse_snapshot
    def observed_parse(text, token, document):
        result["payload"] = json.loads(text)
        return original_parse(text, token, document)
    bulk_snapshot.parse_snapshot = observed_parse
    start = time.perf_counter()
    try:
        with GstarSession("GStarCAD.Application.26") as session:
            result["owned_pid"] = session.owned_pid
            with SourceWorkspace(source) as workspace:
                with session.working_document(workspace) as document:
                    document._bulk_enabled = False
                    t = time.perf_counter()
                    if not args.native_only:
                        result["com"] = asdict(detect_scale_cell(document, DetectionLimits(64, 5000), store.all()))
                    result["com_seconds"] = time.perf_counter() - t
                    t = time.perf_counter()
                    old_log = document.raw.GetVariable("LOGFILEMODE")
                    document.raw.SetVariable("LOGFILEMODE", 1)
                    try:
                        raw = bulk_snapshot.extract_snapshot(document.raw)
                    finally:
                        log = Path(document.raw.GetVariable("LOGFILENAME"))
                        document.raw.SetVariable("LOGFILEMODE", old_log)
                        if log.is_file():
                            result["cad_log"] = log.read_text(encoding="mbcs", errors="replace")[-10000:]
                    result["native_extract_seconds"] = time.perf_counter() - t
                    native = GstarDocument(raw)
                    result["native"] = asdict(detect_scale_cell(native, DetectionLimits(64, 5000), store.all()))
                    result["native_total_seconds"] = time.perf_counter() - t
                    baseline = result.get("com", result["native"])
                    result["max_anchor_error"] = max(abs(baseline["anchor"][k] - result["native"]["anchor"][k]) for k in ("x", "y"))
                    result["same_cell"] = (
                        all(baseline[k] == result["native"][k] for k in ("state", "token", "handle", "rotation_hint"))
                        and result["max_anchor_error"] <= 1e-9
                    )
    except Exception as exc:
        result["error"] = str(exc)
        result["cause"] = str(exc.__cause__)
        result["traceback"] = traceback.format_exc()
    finally:
        result["total_seconds"] = time.perf_counter() - start
        result["sources_unchanged"] = before == (sha256(source), source.stat().st_mtime_ns)
        result["pids_before"] = sorted(pids)
        result["pids_after"] = sorted(_gstar_pids())
        result["owned_closed"] = result.get("owned_pid") not in result["pids_after"]
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "payload"}, default=str))
    return int("error" in result or not result["same_cell"] or not result["sources_unchanged"] or not result["owned_closed"] or not pids <= set(result["pids_after"]))


if __name__ == "__main__":
    raise SystemExit(main())
