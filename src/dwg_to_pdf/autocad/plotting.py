"""Experimental public ActiveX plotting contract, not AutoCAD certification."""
from io import BytesIO
import math
from pathlib import Path

from pypdf import PdfReader

from ..errors import AppError
from ..gstarcad.media_resolver import require_plot_environment
from ..gstarcad.plot_settings import apply_plot_settings
from ..gstarcad.plotter import plot_to_file


def validate_orientation(output: Path) -> None:
    """Do not modify AutoCAD PDF bytes based on another driver's behavior."""
    try:
        reader = PdfReader(BytesIO(output.read_bytes()), strict=True)
        if reader.is_encrypted or len(reader.pages) != 1:
            raise ValueError("unexpected PDF structure")
        page = reader.pages[0]
        width, height = (float(v) * 25.4 / 72 for v in (page.mediabox.width, page.mediabox.height))
        if not all(math.isfinite(v) for v in (width, height)):
            raise ValueError("non-finite PDF dimensions")
        if abs(width - 297.) > .20 or abs(height - 210.) > .20 or page.rotation != 0:
            raise ValueError("unverified AutoCAD paper orientation")
    except Exception as exc:
        raise AppError("E420", "AutoCAD PDF must be unrotated A4 landscape; no automatic correction applied", output) from exc


def plot_pdf(raw, output: Path, window, rotation, preferred_media_names: tuple[str, ...]) -> None:
    try:
        layout = raw.ActiveLayout
        layout.PaperUnits = 1
        media = require_plot_environment(layout, preferred_media_names)
        apply_plot_settings(layout, window, rotation, media)
        plot_to_file(raw, output)
        validate_orientation(output)
    except AppError as exc:
        raise AppError(exc.code, str(exc).replace("GstarCAD", "AutoCAD"), exc.path) from exc
    except Exception as exc:
        raise AppError("E410", "AutoCAD PDF plotting failed", output) from exc
