from types import SimpleNamespace

import pytest

from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from dwg_to_pdf.domain import Point, Rect
from dwg_to_pdf.gstarcad.document import GstarDocument
from dwg_to_pdf.autocad.document import AutoCADDocument


class Collection:
    def __init__(self, items):
        self.items = items
        self.Count = len(items)
        self.IsXRef = False

    def Item(self, index):
        return self.items[index]


def raw_document():
    colored = SimpleNamespace(
        TrueColor=SimpleNamespace(ColorMethod=194, Red=12, Green=34, Blue=56),
        Color=256,
    )
    return SimpleNamespace(Layers=Collection([colored]), Blocks=Collection([]), ActiveLayout=object()), colored


class Layout:
    def GetPlotDeviceNames(self): return ("DWG To PDF.pc3",)
    def RefreshPlotDeviceInfo(self): pass
    def GetPlotStyleTableNames(self): return ("monochrome.ctb",)
    def GetCanonicalMediaNames(self): return ("A4",)
    def GetPaperSize(self): return (297., 210.)
    def SetWindowToPlot(self, lower, upper): self.window = lower.value, upper.value


@pytest.mark.parametrize("document_type", [GstarDocument, AutoCADDocument])
@pytest.mark.parametrize("unreadable_colors", [False, True])
def test_monochrome_plot_keeps_true_color_without_extra_color_traversal(tmp_path, document_type, unreadable_colors):
    raw, colored = raw_document()
    raw.ActiveLayout = Layout()
    raw.GetVariable = lambda name: 2
    raw.SetVariable = lambda name, value: None
    if unreadable_colors:
        class UnreadableCollection:
            @property
            def Count(self):
                raise AssertionError("plot must not inspect color collections")
        raw.Layers = raw.Blocks = UnreadableCollection()

    def driver_plot(path):
        writer = PdfWriter()
        page = writer.add_blank_page(297 * 72 / 25.4, 210 * 72 / 25.4)
        stream = DecodedStreamObject()
        # The driver models a True Color exception to the CTB.
        color = b"1 0 0" if colored.Color == 256 else b"0 0 0"
        stream.set_data(color + b" rg 40 60 20 30 re f")
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.write(Path(path))
        return True

    raw.Plot = SimpleNamespace(PlotToFile=driver_plot)
    output = tmp_path / "out.pdf"
    document_type(raw).plot_pdf(output, Rect(Point(0, 0), Point(420, 297)), 0, ())
    assert colored.Color == 256
    assert raw.ActiveLayout.StyleSheet == "monochrome.ctb"
    assert raw.ActiveLayout.PlotWithPlotStyles is True
    assert raw.ActiveLayout.window == ((0., 0.), (420., 297.))
    assert b"1 0 0 rg" in PdfReader(output, strict=True).pages[0].get_contents().get_data()
