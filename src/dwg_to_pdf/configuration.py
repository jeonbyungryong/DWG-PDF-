from dataclasses import dataclass
import math
from pathlib import Path
import tomllib
from typing import Any

from .errors import AppError
from .cad.selection import ProviderId, validate_prog_id


@dataclass(frozen=True)
class AppConfig:
    prog_id: str | None
    auto_match_enabled: bool
    plotter_name: str
    media_width_mm: float
    media_height_mm: float
    style_sheet: str
    preferred_media_names: tuple[str, ...]
    matching_threshold: float | None
    minimum_score_gap: float | None
    use_native_extraction: bool = True
    cad_provider: ProviderId = "gstarcad"
    allow_experimental_autocad: bool = False
    autocad_pc3_path: Path | None = None


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _optional_score(value: Any, field: str) -> float | None:
    if value is None:
        return None
    result = _require_number(value, field)
    if not 0 < result <= 1:
        raise ValueError(f"{field} must be greater than 0 and at most 1")
    return result


def _parse_config(path: Path) -> AppConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    provider, prog_id, allow_experimental = _parse_cad(data)
    matching = data["matching"]
    use_target_saved_window = matching.get("use_target_saved_window", False)
    if not isinstance(use_target_saved_window, bool):
        raise ValueError("matching.use_target_saved_window must be a boolean")
    if use_target_saved_window:
        raise AppError("E001", "target saved Plot Window must remain disabled", path)
    enabled = matching["auto_match_enabled"]
    if not isinstance(enabled, bool):
        raise ValueError("matching.auto_match_enabled must be a boolean")
    native = matching.get("use_native_extraction", True)
    if not isinstance(native, bool):
        raise ValueError("matching.use_native_extraction must be a boolean")
    threshold = _optional_score(
        matching.get("matching_threshold"), "matching.matching_threshold"
    )
    gap = _optional_score(
        matching.get("minimum_score_gap"), "matching.minimum_score_gap"
    )
    if enabled and (threshold is None or gap is None):
        raise AppError("E001", "enabled auto-match requires numeric calibrated threshold and gap", path)
    plot = data["plot"]
    plotter_name = _require_string(plot["plotter_name"], "plot.plotter_name")
    if plotter_name != "DWG To PDF.pc3":
        raise AppError("E001", "only the approved DWG To PDF.pc3 plotter is allowed", path)
    pc3_path = None
    if "autocad_pc3_path" in plot:
        pc3_path = Path(_require_string(plot["autocad_pc3_path"], "plot.autocad_pc3_path"))
        if (provider != "autocad" or not pc3_path.is_absolute()
                or pc3_path.name.casefold() != "dwg to pdf.pc3" or not pc3_path.is_file()):
            raise AppError("E001", "AutoCAD PC3 override must be an existing absolute DWG To PDF.pc3 path", path)
        pc3_path = pc3_path.resolve(strict=True)
    media_width_mm = _require_number(plot["media_width_mm"], "plot.media_width_mm")
    media_height_mm = _require_number(plot["media_height_mm"], "plot.media_height_mm")
    if (media_width_mm, media_height_mm) != (297.0, 210.0):
        raise AppError("E001", "only A4 landscape 297 x 210 mm is allowed", path)
    style_sheet = _require_string(plot["style_sheet"], "plot.style_sheet")
    if style_sheet.casefold() != "monochrome.ctb":
        raise AppError("E001", "only the approved monochrome.ctb style sheet is allowed", path)
    preferred_media_names = plot.get("preferred_media_names", [])
    if not isinstance(preferred_media_names, list) or not all(
        isinstance(name, str) for name in preferred_media_names
    ):
        raise ValueError("plot.preferred_media_names must be an array of strings")
    return AppConfig(
        prog_id=prog_id,
        auto_match_enabled=enabled,
        plotter_name=plotter_name,
        media_width_mm=media_width_mm,
        media_height_mm=media_height_mm,
        style_sheet=style_sheet,
        preferred_media_names=tuple(preferred_media_names),
        matching_threshold=threshold,
        minimum_score_gap=gap,
        use_native_extraction=native,
        cad_provider=provider,
        allow_experimental_autocad=allow_experimental,
        autocad_pc3_path=pc3_path,
    )


def _parse_cad(data: dict[str, Any]) -> tuple[ProviderId, str | None, bool]:
    legacy = data.get("gstarcad")
    if "cad" not in data:
        return "gstarcad", validate_prog_id(data["gstarcad"]["prog_id"], "gstarcad"), False
    cad = data["cad"]
    provider = cad.get("provider", "gstarcad")
    if provider not in ("gstarcad", "autocad"):
        raise ValueError("cad.provider must be gstarcad or autocad")
    allowed = cad.get("allow_experimental_autocad", False)
    if type(allowed) is not bool:
        raise ValueError("cad.allow_experimental_autocad must be a boolean")
    prog_id = validate_prog_id(cad["prog_id"], provider) if "prog_id" in cad else None
    if legacy is not None:
        old = validate_prog_id(legacy["prog_id"], "gstarcad")
        if provider != "gstarcad" or (prog_id is not None and old.casefold() != prog_id.casefold()):
            raise ValueError("conflicting cad/gstarcad sections; remove or migrate the legacy section")
        prog_id = prog_id or old
    return provider, prog_id, allowed


def load_config(path: Path) -> AppConfig:
    try:
        return _parse_config(path)
    except AppError as exc:
        if exc.path is None and exc.code == "E001":
            raise AppError(exc.code, str(exc), path) from exc
        raise
    except (
        AttributeError,
        OSError,
        tomllib.TOMLDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise AppError("E001", f"invalid configuration: {exc}", path) from exc
