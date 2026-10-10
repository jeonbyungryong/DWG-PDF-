"""Prepare validated local AutoCAD settings without a first-run file picker."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import mkdtemp

from ..cad.selection import CadCandidate
from ..configuration import load_config
from ..desktop_settings import _settings_path
from ..errors import AppError
from ..gstarcad.media_resolver import require_plot_environment
from ..runtime_paths import default_profiles_path
from ..templates.profile_store import ProfileStore, require_canonical_profiles
from ..temp_workspace import SourceWorkspace


_PREFERRED_A4 = "ISO_full_bleed_A4_(297.00_x_210.00_MM)"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _query_plotter(session, source: Path) -> tuple[Path, str, str]:
    # COM proxies stay local to this function and are released before Quit.
    try:
        search = str(session.app.Preferences.Files.PrinterConfigPath)
        candidates = {}
        for raw in search.split(";"):
            raw = raw.strip().strip('"')
            if not raw:
                continue
            directory = Path(os.path.expandvars(raw))
            if not directory.is_absolute():
                continue
            path = directory / "DWG To PDF.pc3"
            if path.is_file():
                path = path.resolve(strict=True)
                candidates[os.path.normcase(str(path))] = path
        if len(candidates) != 1:
            raise AppError("E210", "AutoCAD: expected one installed DWG To PDF.pc3")
        pc3 = next(iter(candidates.values()))
        before = (_sha256(pc3), pc3.stat().st_mtime_ns)
    except AppError:
        raise
    except Exception as error:
        raise AppError("E210", "AutoCAD: could not inspect the installed PC3") from error

    with SourceWorkspace(source) as workspace:
        with session.working_document(workspace) as document:
            media = require_plot_environment(document.raw.ActiveLayout, (_PREFERRED_A4,))
    if (_sha256(pc3), pc3.stat().st_mtime_ns) != before:
        raise AppError("E210", "AutoCAD: installed PC3 changed during setup")
    return pc3, before[0], media


def _inspect_plotter(candidate: CadCandidate) -> tuple[Path, str, str]:
    from .com_session import AutoCADSession
    import win32api
    import win32event

    directory = default_profiles_path()
    store = ProfileStore(directory, source_root=directory)
    store.load_all()
    source = require_canonical_profiles(store.all())[0].source_path
    exit_handle = None
    try:
        with AutoCADSession(candidate) as session:
            # Duplicate the proven object, never reopen a potentially reused PID.
            try:
                current = win32api.GetCurrentProcess()
                exit_handle = win32api.DuplicateHandle(
                    current, session._owned_process_handle, current, 0x00100000, False, 0,
                )
                if exit_handle is None:
                    raise ValueError("missing completion handle")
            except Exception as error:
                raise AppError("E201", "AutoCAD: could not capture setup completion handle") from error
            result = _query_plotter(session, source)
    finally:
        if exit_handle is not None:
            try:
                # The existing session may request an asynchronous forced exit.
                # Do not start conversion until that same object is terminated.
                if win32event.WaitForSingleObject(exit_handle, 30_000) != 0:
                    raise AppError("E201", "AutoCAD: initial setup session did not exit")
            except AppError:
                raise
            except Exception as error:
                raise AppError("E201", "AutoCAD: could not confirm setup session exit") from error
            finally:
                win32api.CloseHandle(exit_handle)
    if _sha256(result[0]) != result[1]:
        raise AppError("E210", "AutoCAD: installed PC3 changed after inspection")
    return result


def _write_config(pc3_source: Path, pc3_sha256: str, media: str, candidate: CadCandidate) -> str:
    owned = None
    complete = False
    try:
        before_mtime = pc3_source.stat().st_mtime_ns
        if _sha256(pc3_source) != pc3_sha256:
            raise AppError("E210", "AutoCAD: installed PC3 changed before copy")
        root = _settings_path().parent / "autocad-auto"
        root.mkdir(parents=True, exist_ok=True)
        owned = Path(mkdtemp(prefix="setup-", dir=root)).resolve(strict=True)
        pc3_copy = owned / "DWG To PDF.pc3"
        shutil.copy2(pc3_source, pc3_copy)
        if (_sha256(pc3_source) != pc3_sha256 or _sha256(pc3_copy) != pc3_sha256
                or pc3_source.stat().st_mtime_ns != before_mtime):
            raise AppError("E210", "AutoCAD: PC3 copy is not stable")
        text = (
            '[cad]\nprovider="autocad"\n'
            f'prog_id={json.dumps(candidate.prog_id)}\n'
            'allow_experimental_autocad=true\n'
            '[matching]\nauto_match_enabled=true\nuse_native_extraction=true\n'
            'matching_threshold=1.0\nminimum_score_gap=1.0\nuse_target_saved_window=false\n'
            '[plot]\nplotter_name="DWG To PDF.pc3"\n'
            'media_width_mm=297.0\nmedia_height_mm=210.0\nstyle_sheet="monochrome.ctb"\n'
            f'autocad_pc3_path={json.dumps(pc3_copy.as_posix(), ensure_ascii=False)}\n'
            f'preferred_media_names=[{json.dumps(media, ensure_ascii=False)}]\n'
        )
        config_path = owned / "AutoCAD.toml"
        config_path.write_text(text, encoding="utf-8")
        load_config(config_path)
        complete = True
        return str(config_path)
    except AppError:
        raise
    except (OSError, ValueError) as error:
        raise AppError("E001", "AutoCAD: could not create initial local settings") from error
    finally:
        if owned is not None and not complete:
            # Only our two files and our newly created empty directory are removed.
            for name in ("AutoCAD.toml", "DWG To PDF.pc3"):
                try:
                    (owned / name).unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                owned.rmdir()
            except OSError:
                pass


def prepare_autocad_config(candidate: CadCandidate) -> str:
    if candidate.provider != "autocad":
        raise AppError("E202", "initial AutoCAD setup requires an AutoCAD installation")
    pc3_source, pc3_sha256, media = _inspect_plotter(candidate)
    return _write_config(pc3_source, pc3_sha256, media, candidate)
