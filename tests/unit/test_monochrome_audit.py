import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


def auditor():
    path = Path(__file__).parents[2] / "tools/regression/gstarcad/audit_monochrome.py"
    spec = importlib.util.spec_from_file_location("monochrome_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence(tmp_path, color):
    source = tmp_path / "sample.DWG"
    source.write_bytes(b"AC1032approved fixture")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(297 * 72 / 25.4, 210 * 72 / 25.4)
    stream = DecodedStreamObject()
    stream.set_data(color + b" rg 40 40 100 100 re f")
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)
    scale = {"numerator": "1", "denominator": "1"}
    frame = {"output": str(path), "scale": scale, "rotation": 0,
             "plot_window": {"lower_left": {"x": 0, "y": 0}, "upper_right": {"x": 420, "y": 297}}}
    summary = {"sources_unchanged": True, "owned_pid_closed": True, "user_pids_preserved": True,
               "outcomes": [{"source": "sample.DWG", "source_sha256": digest, "outcome": {"source": str(source), "frames": [frame]}}]}
    manifest = {"cases": [{"file": "sample.DWG", "sha256": digest, "scale": scale, "rotation": 0, "window": [0, 0, 420, 297]}]}
    return summary, manifest


@pytest.mark.parametrize("color,failures", [(b"0 0 0", 0), (b"1 0 0", 1)])
def test_exact_monochrome_audit_does_not_promote_one_sample_to_full_43(tmp_path, color, failures):
    summary, manifest = evidence(tmp_path, color)
    result = auditor().audit(summary, manifest, 1)
    assert result["audited"] == 1 and result["non_monochrome_pdfs"] == failures
    assert result["full_43_audit"] is False


def test_audit_rejects_wrong_window_and_unprotected_source(tmp_path):
    summary, manifest = evidence(tmp_path, b"0 0 0")
    summary["sources_unchanged"] = False
    with pytest.raises(ValueError):
        auditor().audit(summary, manifest, 1)
    summary["sources_unchanged"] = True
    summary["outcomes"][0]["outcome"]["frames"][0]["plot_window"]["lower_left"]["x"] = .002
    with pytest.raises(ValueError):
        auditor().audit(summary, manifest, 1)


def test_audit_rejects_input_outside_approved_hash(tmp_path):
    summary, manifest = evidence(tmp_path, b"0 0 0")
    manifest["cases"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        auditor().audit(summary, manifest, 1)


def test_optimized_python_cannot_bypass_protection_checks(tmp_path):
    summary, manifest = evidence(tmp_path, b"0 0 0")
    summary["sources_unchanged"] = False
    summary_path, manifest_path = tmp_path / "summary.json", tmp_path / "manifest.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    script = Path(__file__).parents[2] / "tools/regression/gstarcad/audit_monochrome.py"
    result = subprocess.run([sys.executable, "-O", str(script), str(summary_path), "--manifest", str(manifest_path), "--expected-count", "1"], capture_output=True, text=True)
    assert result.returncode != 0 and "protection failed" in result.stderr
