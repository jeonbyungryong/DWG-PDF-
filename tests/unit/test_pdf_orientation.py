import importlib
import importlib.util
from io import BytesIO

from pypdf import PdfWriter, PdfReader
from pypdf.generic import DecodedStreamObject, NameObject
import pypdfium2 as pdfium
import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.pdf_validator import validate_pdf


def normalize(path, rotation):
    name = "dwg_to_pdf.pdf_orientation"
    assert importlib.util.find_spec(name), "vector page orientation correction is missing"
    return importlib.import_module(name).normalize_portrait_plot(path, rotation)


def rectangle_pdf(path, width=595, height=842):
    writer = PdfWriter()
    page = writer.add_blank_page(width, height)
    content = DecodedStreamObject()
    content.set_data(b"0 0 0 rg 40 60 20 30 re f")
    page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as out:
        writer.write(out)


@pytest.mark.parametrize("rotation,black_xy", [(90, (75, 50)), (270, (767, 545))])
def test_quarter_turn_portrait_becomes_upright_vector_landscape(tmp_path, rotation, black_xy):
    path = tmp_path / "quarter.pdf"
    rectangle_pdf(path)
    normalize(path, rotation)
    validate_pdf(path)
    reader = PdfReader(BytesIO(path.read_bytes()))
    assert reader.pages[0].rotation == 0
    assert b" re" in reader.pages[0].get_contents().get_data()
    doc = pdfium.PdfDocument(path.read_bytes())
    page = doc[0]
    bitmap = page.render(scale=1)
    image = bitmap.to_pil()
    try:
        assert max(image.getpixel(black_xy)[:3]) < 20
        assert min(image.getpixel((300, 200))[:3]) > 240
    finally:
        image.close()
        bitmap.close()
        page.close()
        doc.close()


def test_landscape_output_is_byte_preserved(tmp_path):
    path = tmp_path / "landscape.pdf"
    rectangle_pdf(path, 842, 595)
    before = path.read_bytes()
    normalize(path, 90)
    assert path.read_bytes() == before


def test_wrong_size_is_not_rescaled_or_accepted(tmp_path):
    path = tmp_path / "wrong.pdf"
    rectangle_pdf(path, 500, 700)
    before = path.read_bytes()
    with pytest.raises(AppError):
        normalize(path, 90)
    assert path.read_bytes() == before


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_landscape_with_unexpected_rotation_fails_closed(tmp_path, rotation):
    path = tmp_path / "metadata.pdf"
    writer = PdfWriter()
    writer.add_blank_page(842, 595).rotate(rotation)
    with path.open("wb") as out:
        writer.write(out)
    before = path.read_bytes()
    with pytest.raises(AppError):
        normalize(path, 90)
    assert path.read_bytes() == before
