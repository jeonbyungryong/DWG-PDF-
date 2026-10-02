"""Validate the packaged CLI in a subprocess without development PYTHONPATH."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dwg_to_pdf.gstarcad.com_session import _gstar_pids
from dwg_to_pdf.temp_workspace import sha256
from dwg_to_pdf.pdf_validator import validate_pdf
from dataclasses import asdict


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--exe", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-exit", type=int, default=0)
    p.add_argument("--expected-pdfs", nargs="+", required=True)
    p.add_argument("inputs", type=Path, nargs="+")
    args = p.parse_args()
    inputs = [path.resolve(strict=True) for path in args.inputs]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    identity = lambda path: (sha256(path), path.stat().st_mtime_ns)
    before = {str(path): identity(path) for path in inputs}
    pids_before = _gstar_pids()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    start = time.perf_counter()
    completed = subprocess.run([str(args.exe.resolve(strict=True)), *(str(p) for p in inputs), "--output", str(output), "--conflict", "overwrite"], capture_output=True, env=env, cwd=output)
    seconds = time.perf_counter() - start
    pids_after = _gstar_pids()
    result = {"exit_code": completed.returncode, "expected_exit_code": args.expected_exit, "seconds": seconds, "stdout": completed.stdout.decode("utf-8", errors="replace"), "stderr": completed.stderr.decode("utf-8", errors="replace"), "source_unchanged": before == {str(path): identity(path) for path in inputs}, "pids_before": sorted(pids_before), "pids_after": sorted(pids_after), "no_new_cad_left": pids_after == pids_before, "pdfs": {name: asdict(validate_pdf(output / name)) for name in args.expected_pdfs}}
    (output / "smoke-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Console code pages may not represent replacement characters in child output.
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return int(completed.returncode != args.expected_exit or not result["source_unchanged"] or not result["no_new_cad_left"])


if __name__ == "__main__":
    raise SystemExit(main())
