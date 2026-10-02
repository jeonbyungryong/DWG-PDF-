from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from pypdf import PdfReader

from .errors import AppError

_POINT_TO_MM = 25.4 / 72.0


@dataclass(frozen=True)
class PdfValidation:
    page_count: int
    width_mm: float
    height_mm: float
    nonblank: bool


def _read_pdf(path: Path) -> tuple[Any, BytesIO]:
    # Keeping the PDF in memory guarantees no source handle survives validation
    # and blocks Windows atomic rename/cleanup.
    buffer = BytesIO(path.read_bytes())
    return PdfReader(buffer, strict=True), buffer


def _render_nonblank(path: Path) -> bool:
    data = path.read_bytes()
    document = pdfium.PdfDocument(data)
    page = None
    bitmap = None
    image = None
    gray = None
    try:
        page = document[0]
        bitmap = page.render(scale=1.0)
        image = bitmap.to_pil()
        gray = image.convert("L")
        histogram = gray.histogram()
        dark_pixels = sum(histogram[:246])
        return dark_pixels >= 8
    finally:
        if gray is not None:
            gray.close()
        if image is not None:
            image.close()
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        document.close()


def validate_pdf(path: Path, *, size_tolerance_mm: float = 0.20) -> PdfValidation:
    path = Path(path)
    try:
        if not math.isfinite(size_tolerance_mm) or size_tolerance_mm <= 0:
            raise ValueError("invalid size tolerance")
        if not path.is_file() or path.stat().st_size < 100:
            raise ValueError("missing or trivial PDF")
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("missing PDF header")
        reader, buffer = _read_pdf(path)
        try:
            if bool(reader.is_encrypted):
                raise ValueError("encrypted PDF")
            page_count = len(reader.pages)
            if page_count != 1:
                raise ValueError("PDF must contain exactly one page")
            box = reader.pages[0].mediabox
            width_mm = float(box.width) * _POINT_TO_MM
            height_mm = float(box.height) * _POINT_TO_MM
        finally:
            buffer.close()
        if not math.isfinite(width_mm) or not math.isfinite(height_mm):
            raise ValueError("non-finite page dimensions")
        if abs(width_mm - 297.0) > size_tolerance_mm or abs(height_mm - 210.0) > size_tolerance_mm:
            raise ValueError("PDF is not A4 landscape")
        if not _render_nonblank(path):
            raise ValueError("PDF is blank")
        return PdfValidation(page_count, width_mm, height_mm, True)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("E420", "PDF 구조 또는 렌더링 검증에 실패했습니다.", path) from exc
