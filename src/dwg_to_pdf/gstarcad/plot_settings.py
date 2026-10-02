from __future__ import annotations

import math
from typing import Any

import pythoncom
from win32com.client import VARIANT

from ..domain import Rect
from ..errors import AppError
from ..templates.plot_window_transform import inverse_plot_rotation

AC_WINDOW = 4
AC_SCALE_TO_FIT = 0
AC_MILLIMETERS = 1
_PLOT_ROTATION_ENUM = {0: 0, 90: 1, 180: 2, 270: 3}


def _point_variant(x: float, y: float) -> Any:
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (float(x), float(y)))


def apply_plot_settings(
    layout: Any,
    window: Rect,
    frame_rotation: object,
    media_name: str,
) -> None:
    if type(frame_rotation) is not int or frame_rotation not in _PLOT_ROTATION_ENUM:
        raise AppError("E307", "지원하지 않는 도곽 회전입니다.")
    coordinates = (
        window.lower_left.x,
        window.lower_left.y,
        window.upper_right.x,
        window.upper_right.y,
    )
    if not all(math.isfinite(value) for value in coordinates):
        raise AppError("E307", "Plot Window 좌표가 유효하지 않습니다.")
    if not isinstance(media_name, str) or not media_name.strip():
        raise AppError("E211", "A4 용지 이름이 유효하지 않습니다.")
    try:
        layout.ConfigName = "DWG To PDF.pc3"
        layout.CanonicalMediaName = media_name
        layout.PaperUnits = AC_MILLIMETERS
        layout.SetWindowToPlot(
            _point_variant(window.lower_left.x, window.lower_left.y),
            _point_variant(window.upper_right.x, window.upper_right.y),
        )
        layout.PlotType = AC_WINDOW
        layout.UseStandardScale = True
        layout.StandardScale = AC_SCALE_TO_FIT
        layout.CenterPlot = True
        layout.StyleSheet = "monochrome.ctb"
        layout.PlotWithLineweights = True
        layout.PlotWithPlotStyles = True
        inverse = inverse_plot_rotation(frame_rotation)
        layout.PlotRotation = _PLOT_ROTATION_ENUM[inverse]
        layout.PlotHidden = False
        layout.PlotViewportBorders = False
        layout.PlotViewportsFirst = True
    except AppError:
        raise
    except Exception as exc:
        raise AppError("E410", "GstarCAD PDF 플롯 설정을 적용할 수 없습니다.") from exc
