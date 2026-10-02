"""Argument-safe offline build preflight and exact asset staging."""
from __future__ import annotations

import argparse, hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from dwg_to_pdf.dependency_audit import require_hashed_lock
from dwg_to_pdf.security_guard import audit_source_tree
from dwg_to_pdf.templates.profile_store import ProfileStore, require_canonical_profiles

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", required=True, type=Path)
    p.add_argument("--assets", required=True, type=Path)
    args = p.parse_args()
    source_root = args.source_root.resolve(strict=True)
    assets = args.assets.resolve(strict=False)
    expected = (ROOT / "packaging" / "bundle-assets").resolve(strict=False)
    if assets != expected or expected.parent != (ROOT / "packaging").resolve(strict=True):
        raise ValueError("managed asset path is invalid")
    if assets.exists(): shutil.rmtree(assets)
    assets.mkdir(parents=True)
    audit_source_tree(ROOT / "src" / "dwg_to_pdf"); require_hashed_lock(ROOT / "requirements.lock")
    profiles_dir = ROOT / "template_profiles"
    store = ProfileStore(profiles_dir, source_root=source_root); store.load_all(); require_canonical_profiles(store.all())
    for rel in ("config.toml", "config.example.toml", "README.md"):
        shutil.copy2(ROOT / rel, assets / rel)
    for rel in ("USER_GUIDE_KO.md", "TEST_REPORT.md", "PERFORMANCE_REPORT_20261002.md"):
        shutil.copy2(ROOT / "docs" / rel, assets / rel)
    shutil.copy2(ROOT / "third_party" / "THIRD_PARTY_NOTICES.md", assets / "THIRD_PARTY_NOTICES.md")
    target = assets / "template_profiles"; target.mkdir()
    selected = set()
    for profile_json in sorted(profiles_dir.glob("*.json")):
        raw = json.loads(profile_json.read_text(encoding="utf-8")); name = raw["source"]["path"]
        if name in selected: raise ValueError("duplicate profile asset")
        selected.add(name); source = source_root / name
        if hashlib.sha256(source.read_bytes()).hexdigest().casefold() != raw["source"]["sha256"].casefold(): raise ValueError("reference hash changed")
        shutil.copy2(profile_json, target / profile_json.name); shutil.copy2(source, target / name)
    if len(selected) != 13: raise ValueError("expected exactly 13 template assets")
    return 0

if __name__ == "__main__": raise SystemExit(main())
