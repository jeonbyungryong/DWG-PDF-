"""Experimental public ActiveX plotting contract, not AutoCAD certification."""
from io import BytesIO
import math
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import NameObject, NumberObject


from .readiness import wait_for_document_ready
from ..errors import AppError
from ..pdf_reader import read_pdf
from ..gstarcad.media_resolver import require_plot_environment
from ..gstarcad.plot_settings import apply_plot_settings
from ..gstarcad.plotter import plot_to_file


def normalize_verified_orientation(output: Path, frame_rotation: int, *, reported_version: str | None) -> None:
    """Handle the measured AutoCAD 2021 driver pattern; preserve vector content."""
    try:
        reader = read_pdf(output.read_bytes(), allow_duplicate_page_mode=True)
        if reader.is_encrypted or len(reader.pages) != 1:
            raise ValueError("unexpected PDF structure")
        page = reader.pages[0]
        if page.rotation == 0:
            return
        if (reported_version != "24.0s (LMS Tech)" or type(frame_rotation) is not int
                or frame_rotation not in (90, 180, 270)
                or page.rotation != (-frame_rotation) % 360):
            raise ValueError("unverified AutoCAD rotation pattern")
        width, height = (float(v) * 25.4 / 72 for v in (page.mediabox.width, page.mediabox.height))
        if not all(math.isfinite(v) for v in (width, height)) or abs(width - 297.) > .20 or abs(height - 210.) > .20:
            raise ValueError("unverified AutoCAD paper dimensions")
        content = page.get_contents().get_data()
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        writer.pages[0][NameObject("/Rotate")] = NumberObject(0)
        if writer.pages[0].get_contents().get_data() != content:
            raise ValueError("vector content changed")
        buffer = BytesIO()
        writer.write(buffer)
        output.write_bytes(buffer.getvalue())
    except Exception as exc:
        raise AppError("E420", "AutoCAD PDF rotation does not match the measured 2021 driver contract", output) from exc


def validate_orientation(output: Path) -> None:
    """Do not modify AutoCAD PDF bytes based on another driver's behavior."""
    try:
        reader = read_pdf(output.read_bytes(), allow_duplicate_page_mode=True)
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


def plot_pdf(raw, output: Path, window, rotation, preferred_media_names: tuple[str, ...], *, plot_config: Path | None = None) -> None:
    try:
        layout = raw.ActiveLayout
        media = require_plot_environment(layout, preferred_media_names)
        apply_plot_settings(layout, window, rotation, media)
        # Measured with all four angles on AutoCAD 2021. Its content needs the
        # direct enum, unlike the shared GstarCAD inverse mapping.
        layout.PlotRotation = rotation // 90
        if plot_config is None:
            plot_to_file(raw, output, before_background_restore=lambda: wait_for_document_ready(raw))
        else:
            plot_to_file(raw, output, plot_config=plot_config,
                before_background_restore=lambda: wait_for_document_ready(raw))
        normalize_verified_orientation(output, rotation,
            reported_version=getattr(getattr(raw, "Application", None), "Version", None))
        validate_orientation(output)
    except AppError as exc:
        raise AppError(exc.code, str(exc).replace("GstarCAD", "AutoCAD"), exc.path) from exc
    except Exception as exc:
        raise AppError("E410", "AutoCAD PDF plotting failed", output) from exc
