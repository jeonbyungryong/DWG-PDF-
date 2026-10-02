"""Opt-in real CAD benchmark. Copies originals; never edits their contents.

Run with --code-root pointing to a checkout for baseline/optimized comparisons.
--probe-com adds diagnostic overhead and is not a throughput measurement.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import functools
import json
from pathlib import Path
import sys
import time
import shutil


def benchmark_passed(summary):
    return bool(
        summary["outcomes"]
        and not any("error" in item for item in summary["outcomes"])
        and summary["sources_unchanged"]
        and summary["owned_pid_closed"]
        and set(summary["user_pids_before"]) <= set(summary["user_pids_after"])
    )


class ComProbe:
    def __init__(self, raw, stats, definitions, label="document"):
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_stats", stats)
        object.__setattr__(self, "_definitions", definitions)
        object.__setattr__(self, "_label", label)

    def _record(self, name, start, failed=False):
        stat = self._stats.setdefault(name, {"count": 0, "seconds": 0.0, "failed": 0})
        stat["count"] += 1
        stat["seconds"] += time.perf_counter() - start
        stat["failed"] += int(failed)

    def _wrap(self, value, label):
        if isinstance(value, (tuple, list)):
            return tuple(self._wrap(item, label) for item in value)
        if hasattr(value, "_oleobj_"):
            return ComProbe(value, self._stats, self._definitions, label)
        return value

    def __getattr__(self, name):
        start = time.perf_counter()
        try:
            value = getattr(self._raw, name)
        except Exception:
            self._record("get:" + name, start, True)
            raise
        self._record("get:" + name, start)
        if hasattr(value, "_oleobj_"):
            return self._wrap(value, name)
        if callable(value):
            def invoke(*args, **kwargs):
                start = time.perf_counter()
                failed = False
                try:
                    result = value(*args, **kwargs)
                except Exception:
                    failed = True
                    raise
                finally:
                    self._record("call:" + name, start, failed)
                if self._label == "Blocks" and name == "Item":
                    self._definitions[str(args[0])] += 1
                return self._wrap(result, name)
            return invoke
        return self._wrap(value, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, help="DWG inputs, when different from approved template assets")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--names", nargs="*")
    parser.add_argument("--probe-com", action="store_true")
    parser.add_argument("--retain-rejected-pdf", action="store_true", help="Preserve diagnostic copies of rejected outputs")
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root / "src"))
    import dwg_to_pdf.conversion_service as service_module
    from dwg_to_pdf.configuration import load_config
    from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
    from dwg_to_pdf.temp_workspace import sha256
    from dwg_to_pdf.templates.profile_store import ProfileStore
    from dwg_to_pdf.pdf_validator import validate_pdf

    events, current = [], {"name": "batch"}
    com_stats, definitions, failure_details = {}, {}, {}
    if args.retain_rejected_pdf:
        original_publish = service_module.publish_pdf
        def diagnosed_publish(temporary, final):
            folder = args.result.parent / (args.result.stem + "-rejected")
            folder.mkdir(parents=True, exist_ok=True)
            copy = folder / Path(final).name
            shutil.copy2(temporary, copy)
            result = original_publish(temporary, final)
            copy.unlink()
            return result
        service_module.publish_pdf = diagnosed_publish
    def instrument(owner, name):
        original = getattr(owner, name)
        @functools.wraps(original)
        def wrapped(*a, **kw):
            start = time.perf_counter()
            raw = None
            if name == "detect_scale_cell" and args.probe_com:
                raw = a[0].raw
                stats = com_stats.setdefault(current["name"], {})
                visits = definitions.setdefault(current["name"], Counter())
                a[0].raw = ComProbe(raw, stats, visits)
            try:
                return original(*a, **kw)
            except Exception as exc:
                trace = exc.__traceback__
                while trace:
                    if trace.tb_frame.f_code.co_name == "detect_scale_cell":
                        local = trace.tb_frame.f_locals
                        failure_details[current["name"]] = {"value_cell_objects": list(local.get("value_by_key", {}).values())}
                    trace = trace.tb_next
                raise
            finally:
                if raw is not None:
                    a[0].raw = raw
                event = {"source": current["name"], "stage": name, "seconds": time.perf_counter() - start}
                events.append(event)
                print(json.dumps(event), flush=True)
        setattr(owner, name, wrapped)
    for name in ("require_stable", "detect_scale_cell", "choose_profile_by_structure", "require_plot_environment", "apply_plot_settings", "plot_to_file", "publish_pdf"):
        instrument(service_module, name)
    for name in ("__enter__", "_open_working_copy", "close_document", "_release"):
        instrument(GstarSession, name)
    config = load_config(args.code_root / "config.toml")
    store = ProfileStore(args.code_root / "template_profiles", source_root=args.source_root)
    store.load_all()
    input_root = args.input_root or args.source_root
    sources = [input_root / name for name in args.names] if args.names else sorted(input_root.glob("*.DWG"))
    args.result.parent.mkdir(parents=True, exist_ok=True)
    output = args.result.parent / (args.result.stem + "-pdf")
    output.mkdir(exist_ok=True)
    identity = lambda p: (sha256(p), p.stat().st_mtime_ns)
    before = {str(p): identity(p) for p in sources}
    pids_before = _gstar_pids()
    service = service_module.ConversionService(config, store)
    outcomes = []
    owned_pid = None
    start = time.perf_counter()
    try:
        with GstarSession(config.prog_id) as session:
            owned_pid = session.owned_pid
            for source in sources:
                current["name"] = source.name
                file_start = time.perf_counter()
                try:
                    outcome = service.convert_in_session(session, source, output, "overwrite")
                    validation = validate_pdf(outcome.frames[0].output)
                    outcomes.append({"source": source.name, "outcome": asdict(outcome), "pdf": asdict(validation), "seconds": time.perf_counter() - file_start})
                except Exception as exc:
                    outcomes.append({"source": source.name, "error": str(exc), "cause": str(exc.__cause__), "code": getattr(exc, "code", None), "seconds": time.perf_counter() - file_start})
                print(json.dumps(outcomes[-1], default=str), flush=True)
            current["name"] = "batch"
    finally:
        pids_after = _gstar_pids()
        summary = {"code_root": str(args.code_root), "probe_com": args.probe_com, "batch_seconds": time.perf_counter()-start, "sources_unchanged": before == {str(p): identity(p) for p in sources}, "user_pids_before": sorted(pids_before), "user_pids_after": sorted(pids_after), "owned_pid": owned_pid, "owned_pid_closed": owned_pid not in pids_after, "outcomes": outcomes, "events": events, "com": com_stats, "definitions": definitions}
        summary["user_pids_preserved"] = pids_before <= pids_after
        summary["failure_details"] = failure_details
        args.result.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print("RESULT=" + str(args.result), flush=True)
    return int(not benchmark_passed(summary))


if __name__ == "__main__":
    raise SystemExit(main())
