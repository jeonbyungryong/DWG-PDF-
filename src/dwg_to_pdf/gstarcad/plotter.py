from __future__ import annotations

import math
from pathlib import Path
import time
from typing import Any

from ..errors import AppError


def _resolve_path(path: Path) -> Path:
    return path.resolve(strict=False)


def _path_exists(path: Path) -> bool:
    return path.exists()


def _make_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _stat_path(path: Path):
    return path.stat()


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _wait_for_stable_pdf(
    path: Path,
    *,
    checks: int,
    interval_sec: float,
    stat=None,
    sleep=None,
) -> None:
    if type(checks) is not int or checks < 1:
        raise ValueError("stability_checks must be a positive integer")
    if not math.isfinite(interval_sec) or interval_sec < 0:
        raise ValueError("stability_interval_sec must be finite and non-negative")
    previous: tuple[int, int] | None = None
    stable = 0
    attempts = max(checks + 4, checks * 3)
    stat_fn = _stat_path if stat is None else stat
    sleep_fn = _sleep if sleep is None else sleep
    for _ in range(attempts):
        try:
            details = stat_fn(path)
            current = (details.st_size, details.st_mtime_ns)
        except OSError:
            current = None
        if current is not None and current[0] >= 100:
            if checks == 1 or current == previous:
                stable += 1
                if stable >= checks:
                    return
            else:
                stable = 1
            previous = current
        else:
            stable = 0
            previous = current
        if interval_sec:
            sleep_fn(interval_sec)
    raise AppError("E410", "GstarCAD가 안정된 PDF 파일을 생성하지 못했습니다.", path)


def plot_to_file(
    document: Any,
    output: Path,
    *,
    stability_checks: int = 3,
    stability_interval_sec: float = 0.20,
) -> None:
    requested_output = Path(output)
    resolved_output: Path | None = None
    owned_output = False
    previous_background: object | None = None
    background_changed = False
    primary_error: AppError | None = None
    try:
        resolved_output = _resolve_path(requested_output)
        if resolved_output.suffix.casefold() != ".pdf" or _path_exists(resolved_output):
            raise AppError(
                "E410", "플롯 대상은 존재하지 않는 임시 PDF 경로여야 합니다.", resolved_output
            )
        owned_output = True
        _make_dir(resolved_output.parent)
        previous_background = document.GetVariable("BACKGROUNDPLOT")
        document.SetVariable("BACKGROUNDPLOT", 0)
        background_changed = True
        result = document.Plot.PlotToFile(str(resolved_output))
        if result is not True and result != 1:
            raise AppError("E410", "GstarCAD PDF 플롯 호출이 실패했습니다.", resolved_output)
        _wait_for_stable_pdf(
            resolved_output,
            checks=stability_checks,
            interval_sec=stability_interval_sec,
        )
    except AppError as exc:
        primary_error = exc
    except Exception as exc:
        primary_error = AppError("E410", "GstarCAD PDF 플롯에 실패했습니다.", requested_output)
        primary_error.__cause__ = exc
    finally:
        if background_changed:
            try:
                document.SetVariable("BACKGROUNDPLOT", previous_background)
            except Exception as restore_exc:
                if primary_error is None:
                    primary_error = AppError(
                        "E410",
                        "GstarCAD 백그라운드 플롯 설정을 복원하지 못했습니다.",
                        resolved_output or requested_output,
                    )
                    primary_error.__cause__ = restore_exc
                else:
                    primary_error.add_note(
                        f"Background restore failure: {type(restore_exc).__name__}: {restore_exc}"
                    )
        if primary_error is not None and owned_output and resolved_output is not None:
            try:
                _remove_file(resolved_output)
            except OSError as cleanup_exc:
                cleanup_error = AppError(
                    "E410", "실패한 임시 PDF를 정리할 수 없습니다.", resolved_output
                )
                cleanup_error.add_note(
                    f"Primary failure: {type(primary_error).__name__}: {primary_error}"
                )
                cleanup_error.__cause__ = primary_error
                primary_error = cleanup_error
    if primary_error is not None:
        raise primary_error
