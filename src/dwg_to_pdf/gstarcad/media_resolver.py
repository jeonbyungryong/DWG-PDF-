from __future__ import annotations

import math
from typing import Any

from ..errors import AppError


def require_plot_environment(
    layout: Any,
    preferred_names: tuple[str, ...],
    tolerance_mm: float = 0.20,
) -> str:
    """Resolve an installed A4 medium by measured size, not a localized label."""

    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError("tolerance_mm must be positive and finite")
    try:
        devices = {str(name) for name in layout.GetPlotDeviceNames()}
        if "DWG To PDF.pc3" not in devices:
            raise AppError("E210", "DWG To PDF.pc3 is not installed")
        layout.ConfigName = "DWG To PDF.pc3"
        layout.RefreshPlotDeviceInfo()
        styles = {str(name).casefold() for name in layout.GetPlotStyleTableNames()}
        if "monochrome.ctb" not in styles:
            raise AppError("E212", "monochrome.ctb is not installed")

        matches: list[str] = []
        for raw_name in layout.GetCanonicalMediaNames():
            name = str(raw_name)
            layout.CanonicalMediaName = name
            width, height = (float(value) for value in layout.GetPaperSize())
            if not (math.isfinite(width) and math.isfinite(height)):
                raise AppError("E211", f"media {name} reported a non-finite paper size")
            landscape_a4 = abs(width - 297.0) <= tolerance_mm and abs(height - 210.0) <= tolerance_mm
            portrait_a4 = abs(width - 210.0) <= tolerance_mm and abs(height - 297.0) <= tolerance_mm
            if landscape_a4 or portrait_a4:
                matches.append(name)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("E211", "could not inspect GstarCAD plot media") from exc

    preferred = [name for name in preferred_names if name in matches]
    if len(preferred) == 1:
        return preferred[0]
    if len(preferred) > 1:
        raise AppError("E211", "multiple preferred A4 media are installed")
    if len(matches) != 1:
        raise AppError("E211", f"expected one A4 media by dimensions, found {len(matches)}")
    return matches[0]
