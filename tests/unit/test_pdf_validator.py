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


def _duplicate_view_mode_pdf(path, extra=b""):
    # Hand-authored driver-shaped fixture; xref offsets are genuine.
    content = b"0 0 0 rg 40 60 20 30 re f"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R /PageMode /UseOC /PageMode /UseOutlines " + extra + b" >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 5\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    path.write_bytes(data)


def test_autocad_view_mode_duplicates_preserve_bytes_and_geometry(tmp_path):
    path = tmp_path / "autocad.pdf"
    _duplicate_view_mode_pdf(path)
    before = path.read_bytes()
    result = validate_pdf(path, allow_duplicate_page_mode=True)
    assert result.page_count == 1 and result.nonblank
    assert result.width_mm == pytest.approx(297.04, abs=.2)
    assert path.read_bytes() == before


def test_default_validation_remains_strict_for_duplicate_view_mode(tmp_path):
    path = tmp_path / "strict.pdf"
    _duplicate_view_mode_pdf(path)
    with pytest.raises(AppError):
        validate_pdf(path)


@pytest.mark.parametrize("extra", [b"/Pages 2 0 R", b"/Nested << /A 1 /A 2 >>", b"/PageMode /NotAViewMode"])
def test_autocad_compatibility_rejects_other_ambiguous_pdf_entries(tmp_path, extra):
    path = tmp_path / "ambiguous.pdf"
    _duplicate_view_mode_pdf(path, extra)
    with pytest.raises(AppError):
        validate_pdf(path, allow_duplicate_page_mode=True)


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
