"""Exercise the shipped build entry point with controlled external tools."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).parents[2]
ENGINES = [path for path in (
    shutil.which("pwsh"),
    str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
) if path and Path(path).is_file()]


@pytest.mark.skipif(os.name != "nt" or not ENGINES, reason="Windows PowerShell required")
@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("verification_exit", [0, 1, None])
def test_build_only_publishes_zip_after_successful_verification(tmp_path, engine, verification_exit):
    packaging = tmp_path / "packaging"
    assets = packaging / "bundle-assets"
    assets.mkdir(parents=True)
    shutil.copyfile(ROOT / "packaging/build.ps1", packaging / "build.ps1")
    if verification_exit is None:
        # Real verifier deliberately receives a bundle missing its executable.
        shutil.copyfile(ROOT / "packaging/verify_bundle.ps1", packaging / "verify_bundle.ps1")
    else:
        (packaging / "verify_bundle.ps1").write_text(
            f"param($BundlePath, $ChecksumsPath)\nexit {verification_exit}\n", encoding="ascii"
        )
    # The expensive external Python preflight/freezer is not the behavior under test.
    fake_python = tmp_path / "python-stub.cmd"
    fake_python.write_text("@exit /b 0\n", encoding="ascii")
    deps = tmp_path / "dependencies"
    cache = deps / "__pycache__"
    cache.mkdir(parents=True)
    for name in ("typing_extensions", "pythoncom", "pywintypes"):
        (cache / f"{name}.cpython-312.pyc").write_bytes(b"fixture")
    bundle = tmp_path / "dist/dwg-to-pdf-validation"
    bundle.mkdir(parents=True)
    (bundle / "fixture.txt").write_text("fixture", encoding="ascii")
    (bundle.parent / "dwg-to-pdf-validation-checksums.csv").write_text("fixture", encoding="ascii")
    env = {**os.environ, "PYTHONPATH": str(deps), "DWG_TO_PDF_TEMPLATE_SOURCE_ROOT": str(tmp_path)}
    result = subprocess.run(
        [engine, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
         str(packaging / "build.ps1"), "-Python", str(fake_python)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    zip_path = bundle.parent / "dwg-to-pdf-validation.zip"
    if verification_exit != 0:
        assert result.returncode != 0, result.stdout + result.stderr
        assert not zip_path.exists()
        assert "VALIDATION_ZIP=" not in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert zip_path.is_file()
        assert "VALIDATION_ZIP=" in result.stdout
