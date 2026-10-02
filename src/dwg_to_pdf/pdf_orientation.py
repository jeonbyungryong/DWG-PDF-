"""Normalize quarter-turn GstarCAD portrait output without rasterizing it."""
from io import BytesIO
import math
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .errors import AppError


def normalize_portrait_plot(path: Path, frame_rotation: int) -> None:
    if frame_rotation not in (90, 270):
        return
    try:
        reader = PdfReader(BytesIO(path.read_bytes()), strict=True)
        if reader.is_encrypted or len(reader.pages) != 1:
            raise ValueError("unexpected PDF page structure")
        page = reader.pages[0]
        width, height = float(page.mediabox.width) * 25.4 / 72, float(page.mediabox.height) * 25.4 / 72
        if not all(math.isfinite(v) for v in (width, height)):
            raise ValueError("invalid PDF dimensions")
        if abs(width - 297) <= .20 and abs(height - 210) <= .20:
            if page.rotation != 0:
                raise ValueError("unexpected landscape page rotation")
            return
        if abs(width - 210) > .20 or abs(height - 297) > .20:
            raise ValueError("quarter-turn output must be A4")
        writer = PdfWriter()
        page = writer.add_page(page)
        # This GstarCAD driver physically turns the paper for 90/270 degrees
        # while leaving the plotted frame sideways. Bake the correction into
        # vector content and every page box, keeping the landscape validator.
        if page.rotation == 0:
            page.rotate(frame_rotation)
        elif page.rotation not in (90, 270):
            raise ValueError("unexpected portrait page rotation")
        page.transfer_rotation_to_content()
        output = BytesIO()
        writer.write(output)
        path.write_bytes(output.getvalue())
    except Exception as exc:
        raise AppError("E420", "회전 PDF의 가로 방향을 정규화할 수 없습니다.", path) from exc
