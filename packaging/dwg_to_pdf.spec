# -*- mode: python ; coding: utf-8 -*-
"""Offline PyInstaller specification for the non-production validation bundle."""

from pathlib import Path
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


ROOT = Path(SPECPATH).parent
ASSETS = Path(os.environ["DWG_TO_PDF_BUNDLE_ASSETS"]).resolve(strict=True)
PROFILE_ASSETS = ASSETS / "template_profiles"

datas = [
    (str(ASSETS / "config.toml"), "."),
    (str(ASSETS / "config.example.toml"), "."),
    (str(ASSETS / "README.md"), "."),
    (str(ASSETS / "USER_GUIDE_KO.md"), "docs"),
    (str(ASSETS / "TEST_REPORT.md"), "docs"),
    (str(ASSETS / "THIRD_PARTY_NOTICES.md"), "third_party"),
    (str(ASSETS / "typing_extensions.pyc"), "."),
    (str(ASSETS / "pythoncom.pyc"), "."),
    (str(ASSETS / "pywintypes.pyc"), "."),
]
datas.extend((str(path), "template_profiles") for path in sorted(PROFILE_ASSETS.iterdir()) if path.is_file())

hiddenimports = []
binaries = []
for package in ("win32com", "pythoncom", "pywintypes", "jsonschema", "pypdf", "pypdfium2", "PIL"):
    hiddenimports.extend(collect_submodules(package))
    datas.extend(collect_data_files(package))
    binaries.extend(collect_dynamic_libs(package))
hiddenimports.extend(["pythoncom", "pywintypes"])

# pythoncom/pywintypes are extension DLL modules, not packages, so the
# package collectors intentionally skip them. Include their resolved origins.
import pythoncom
import pywintypes
for extension in (pythoncom, pywintypes):
    binaries.append((extension.__file__, "."))

a = Analysis(
    [str(ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    runtime_hooks=[str(ROOT / "packaging" / "pyi_rth_pywin32.py")],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name="dwg-to-pdf", console=True, exclude_binaries=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="dwg-to-pdf-validation")
