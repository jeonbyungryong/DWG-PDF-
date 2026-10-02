from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.pdf_validator import validate_pdf


def _image_pdf(path: Path, size: tuple[int, int] = (842, 595), *, blank: bool = False) -> None:
    image = Image.new("RGB", size, "white")
    if not blank:
        ImageDraw.Draw(image).line((20, 20, size[0] - 20, size[1] - 20), fill="black", width=3)
    image.save(path, "PDF", resolution=72.0)
    image.close()


def _blank_pdf(path: Path, width: float = 842, height: float = 595, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    with path.open("wb") as stream:
        writer.write(stream)


@pytest.mark.parametrize("payload", [b"", b"not a pdf", b"%PDF-"])
def test_invalid_header_or_malformed_pdf_is_rejected(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(payload)
    with pytest.raises(AppError) as raised:
        validate_pdf(path)
    assert raised.value.code == "E420"


def test_validator_accepts_single_nonblank_a4_landscape_pdf(tmp_path: Path) -> None:
    path = tmp_path / "valid.pdf"
    _image_pdf(path)
    result = validate_pdf(path)
    assert result.page_count == 1
    assert result.width_mm == pytest.approx(297.04, abs=0.2)
    assert result.height_mm == pytest.approx(209.90, abs=0.2)
    assert result.nonblank is True


@pytest.mark.parametrize(
    ("width", "height", "pages"),
    [(595, 842, 1), (800, 600, 1), (842, 595, 0), (842, 595, 2)],
)
def test_wrong_page_geometry_or_count_is_rejected(
    tmp_path: Path, width: float, height: float, pages: int
) -> None:
    path = tmp_path / "wrong.pdf"
    _blank_pdf(path, width, height, pages)
    with pytest.raises(AppError) as raised:
        validate_pdf(path)
    assert raised.value.code == "E420"


def test_blank_a4_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    _image_pdf(path, blank=True)
    with pytest.raises(AppError) as raised:
        validate_pdf(path)
    assert raised.value.code == "E420"


def test_encrypted_pdf_is_rejected(tmp_path: Path) -> None:
    plain = tmp_path / "plain.pdf"
    encrypted = tmp_path / "encrypted.pdf"
    _blank_pdf(plain)
    reader = PdfReader(plain)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.encrypt("secret")
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(AppError) as raised:
        validate_pdf(encrypted)
    assert raised.value.code == "E420"


def test_nonfinite_page_size_is_rejected_before_render(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"%PDF-" + b"x" * 200)

    class Box:
        width = math.inf
        height = 595

    class Page:
        mediabox = Box()

    class Reader:
        is_encrypted = False
        pages = [Page()]

    monkeypatch.setattr("dwg_to_pdf.pdf_validator._read_pdf", lambda path: (Reader(), BytesIO()))
    with pytest.raises(AppError) as raised:
        validate_pdf(path)
    assert raised.value.code == "E420"


def test_render_failure_is_wrapped_without_raw_exception(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "valid.pdf"
    _image_pdf(path)
    monkeypatch.setattr(
        "dwg_to_pdf.pdf_validator._render_nonblank",
        lambda path: (_ for _ in ()).throw(RuntimeError("renderer internals")),
    )
    with pytest.raises(AppError) as raised:
        validate_pdf(path)
    assert raised.value.code == "E420"
    assert "renderer internals" not in str(raised.value)


def test_validation_releases_windows_file_handles(tmp_path: Path) -> None:
    path = tmp_path / "valid.pdf"
    renamed = tmp_path / "renamed.pdf"
    _image_pdf(path)
    validate_pdf(path)
    path.replace(renamed)
    assert renamed.is_file()
