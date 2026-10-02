from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib


ROOT = Path(__file__).parents[2]


def test_shipped_configs_enable_only_strict_calibrated_matching() -> None:
    for name in ("config.toml", "config.example.toml"):
        config = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))
        matching = config["matching"]
        assert matching["auto_match_enabled"] is True
        assert matching["matching_threshold"] == 1.0
        assert matching["minimum_score_gap"] == 1.0


def test_packaging_scripts_are_offline_and_require_explicit_template_root() -> None:
    build = (ROOT / "packaging" / "build.ps1").read_text(encoding="utf-8").casefold()
    assert "dwg_to_pdf_template_source_root" in build
    for forbidden in ("pip install", "pip.exe", "invoke-webrequest", "curl ", "wget "):
        assert forbidden not in build
    preflight = (ROOT / "packaging" / "preflight.py").read_text(encoding="utf-8")
    assert "preflight.py" in build
    assert "audit_source_tree" in preflight
    assert "require_hashed_lock" in preflight


def test_build_removes_misleading_legacy_standalone_executable() -> None:
    build = (ROOT / "packaging" / "build.ps1").read_text(encoding="utf-8")

    assert "$legacyStandalone = Join-Path $root 'dist\\dwg-to-pdf.exe'" in build
    assert "Remove-Item -LiteralPath $legacyStandalone -Force" in build


def test_packaging_spec_collects_runtime_dependencies_and_validation_data() -> None:
    spec = (ROOT / "packaging" / "dwg_to_pdf.spec").read_text(encoding="utf-8")
    for required in ("collect_data_files", "collect_dynamic_libs", "win32com", "jsonschema", "pypdf", "pypdfium2", "PIL"):
        assert required in spec
    assert "template_profiles" in spec
    assert "config.toml" in spec
    assert "exclude_binaries=True" in spec


def test_bundle_verifier_requires_frozen_self_check_and_runtime_hook_keeps_dll_handle_alive() -> None:
    verify = (ROOT / "packaging" / "verify_bundle.ps1").read_text(encoding="utf-8")
    hook = (ROOT / "packaging" / "pyi_rth_pywin32.py").read_text(encoding="utf-8")
    assert "--self-check" in verify
    assert "_dll_directory_handle" in hook


def test_profiles_reference_exactly_13_existing_external_dwgs_with_matching_hashes() -> None:
    source_root_text = __import__("os").environ.get("DWG_TO_PDF_TEMPLATE_SOURCE_ROOT")
    if not source_root_text:
        return
    source_root = Path(source_root_text)
    profiles = sorted((ROOT / "template_profiles").glob("*.json"))
    assert len(profiles) == 13
    names: set[str] = set()
    for path in profiles:
        profile = json.loads(path.read_text(encoding="utf-8"))
        reference = source_root / profile["source"]["path"]
        assert reference.is_file()
        assert profile["source"]["path"] not in names
        names.add(profile["source"]["path"])
        assert hashlib.sha256(reference.read_bytes()).hexdigest().casefold() == profile["source"]["sha256"].casefold()


def test_docs_state_validation_limits_and_correct_batch_and_blank_na_contracts() -> None:
    text = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "docs/USER_GUIDE_KO.md", "docs/TEST_REPORT.md", "third_party/THIRD_PARTY_NOTICES.md")
    ).casefold()
    for required in ("validation", "blank", "n/a", "one app-owned", "actual 6", "production"):
        assert required in text
    assert "파일마다 별도 process를 사용합니다." not in text


def test_legacy_implementation_plan_marks_one_process_per_file_as_superseded() -> None:
    plan = (ROOT / "docs/superpowers/plans/2026-07-16-dwg-to-pdf-implementation.md").read_text(encoding="utf-8")
    assert "one owned GstarCAD process is created per input DWG" not in plan
    assert "single sequential APP-owned batch session" in plan
    assert "batch-session-scale-fallback-design.md" in plan
