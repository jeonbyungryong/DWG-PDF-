from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from dwg_to_pdf.autocad.plotting import plot_pdf, validate_orientation
from dwg_to_pdf.domain import Rect, Point
from dwg_to_pdf.errors import AppError


def pdf(path, width=842, height=595, rotation=0):
    writer = PdfWriter()
    page = writer.add_blank_page(width, height)
    if rotation:
        page.rotate(rotation)
    content = DecodedStreamObject()
    content.set_data(b"0 0 0 rg 40 60 20 30 re f")
    page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(path)


class Layout:
    def __init__(self):
        self.order = []
        self.media = {"User77": (279.4, 215.9), "unknown-A4": (297., 210.)}
        self.styles = ["monochrome.ctb"]
        self.devices = ["DWG To PDF.pc3"]

    def __setattr__(self, name, value):
        if name == "PlotType":
            self.order.append("PlotType")
        super().__setattr__(name, value)

    def GetPlotDeviceNames(self): return self.devices
    def RefreshPlotDeviceInfo(self): pass
    def GetPlotStyleTableNames(self): return self.styles
    def GetCanonicalMediaNames(self): return tuple(self.media)
    def GetPaperSize(self): return self.media[self.CanonicalMediaName]
    def SetWindowToPlot(self, lower, upper):
        self.order.append("Window")
        self.window = (lower.value, upper.value)


@pytest.mark.parametrize("rotation,expected", [(0, 0), (90, 1), (180, 2), (270, 3)])
def test_four_rotations_autocad_mapping_and_measured_media(tmp_path, monkeypatch, rotation, expected):
    layout = Layout()
    output = tmp_path / "plot.pdf"
    calls = []
    def plot(path):
        pdf(Path(path))
        calls.append(Path(path).read_bytes())
        return True
    raw = SimpleNamespace(ActiveLayout=layout, GetVariable=lambda name: 2,
        SetVariable=lambda name, value: None, Plot=SimpleNamespace(PlotToFile=plot),
        Application=SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=True)))
    monkeypatch.setattr("dwg_to_pdf.pdf_orientation.normalize_portrait_plot", lambda *args: pytest.fail("AutoCAD must not normalize Gstar output"))
    window = Rect(Point(1, 2), Point(301, 202))
    plot_pdf(raw, output, window, rotation, ("User77",))
    assert layout.CanonicalMediaName == "unknown-A4"
    assert layout.GetPaperSize() == (297., 210.)
    assert layout.window == ((1., 2.), (301., 202.))
    assert layout.order == ["Window", "PlotType"]
    assert layout.PlotRotation == expected
    assert output.read_bytes() == calls[0]


@pytest.mark.parametrize("frame_rotation,pdf_rotation", [(90,270),(180,180),(270,90)])
def test_verified_2021_rotation_metadata_removed_without_changing_vectors(tmp_path, frame_rotation, pdf_rotation):
    from dwg_to_pdf.autocad.plotting import normalize_verified_orientation
    from dwg_to_pdf.pdf_reader import read_pdf
    output=tmp_path/'verified.pdf'
    pdf(output,rotation=pdf_rotation)
    content=read_pdf(output.read_bytes()).pages[0].get_contents().get_data()
    normalize_verified_orientation(output,frame_rotation,reported_version="24.0s (LMS Tech)")
    reader=read_pdf(output.read_bytes())
    assert reader.pages[0].rotation==0
    assert reader.pages[0].get_contents().get_data()==content
    validate_orientation(output)


@pytest.mark.parametrize("version,frame_rotation,pdf_rotation", [("25.0",90,270),("24.0s (LMS Tech)",90,90),("24.0s (LMS Tech)",0,180)])
def test_unverified_rotation_is_rejected_without_changing_pdf(tmp_path,version,frame_rotation,pdf_rotation):
    from dwg_to_pdf.autocad.plotting import normalize_verified_orientation
    output=tmp_path/'unverified.pdf'; pdf(output,rotation=pdf_rotation)
    before=output.read_bytes()
    with pytest.raises(AppError):
        normalize_verified_orientation(output,frame_rotation,reported_version=version)
    assert output.read_bytes()==before


@pytest.mark.parametrize("width,height,rotation", [(595, 842, 0), (842, 595, 90), (842, 595, 180), (500, 500, 0)])
def test_portrait_or_unexplained_rotation_e420(tmp_path, width, height, rotation):
    output = tmp_path / "bad.pdf"
    pdf(output, width, height, rotation)
    before = output.read_bytes()
    with pytest.raises(AppError) as error:
        validate_orientation(output)
    assert error.value.code == "E420"
    assert output.read_bytes() == before


@pytest.mark.parametrize("missing,code", [("styles", "E212"), ("devices", "E210"), ("media", "E211")])
def test_missing_ctb_pc3_or_letter_only_fails_before_plot(tmp_path, missing, code):
    layout = Layout()
    setattr(layout, missing, {"User77": (279.4, 215.9)} if missing == "media" else [])
    raw = SimpleNamespace(ActiveLayout=layout)
    with pytest.raises(AppError) as error:
        plot_pdf(raw, tmp_path / "absent.pdf", Rect(Point(0, 0), Point(1, 1)), 0, ("User77",))
    assert error.value.code == code
    assert not (tmp_path / "absent.pdf").exists()


def test_invalid_pdf_rejected(tmp_path):
    output = tmp_path / "invalid.pdf"
    output.write_bytes(b"invalid")
    with pytest.raises(AppError) as error:
        validate_orientation(output)
    assert error.value.code == "E420"


def test_plot_succeeds_when_driver_requires_refresh_before_paper_units(tmp_path):
    class RefreshRequiredLayout(Layout):
        refreshed = False
        def RefreshPlotDeviceInfo(self):
            self.refreshed = True
        def __setattr__(self, name, value):
            if name == "PaperUnits" and not self.refreshed:
                raise ValueError("AutoCAD Invalid input before device refresh")
            super().__setattr__(name, value)
    layout = RefreshRequiredLayout()
    output = tmp_path / "plot.pdf"
    def plot(path):
        pdf(Path(path))
        return True
    raw = SimpleNamespace(ActiveLayout=layout, GetVariable=lambda name: 2,
        SetVariable=lambda name, value: None, Plot=SimpleNamespace(PlotToFile=plot),
        Application=SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=True)))
    plot_pdf(raw, output, Rect(Point(1, 2), Point(301, 202)), 0, ())
    validate_orientation(output)


def test_private_pc3_is_passed_to_plot_without_changing_installed_device(tmp_path):
    from dwg_to_pdf.autocad.document import AutoCADDocument
    output = tmp_path / "plot.pdf"
    pc3 = tmp_path / "DWG To PDF.pc3"
    pc3.write_bytes(b"private plotter")
    calls = []
    def plot(path, config):
        calls.append(config)
        pdf(Path(path))
        return True
    raw = SimpleNamespace(ActiveLayout=Layout(), GetVariable=lambda name: 2,
        SetVariable=lambda name, value: None, Plot=SimpleNamespace(PlotToFile=plot),
        Application=SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=True)))
    document = AutoCADDocument(raw)
    raw.Layers = raw.Blocks = SimpleNamespace(Count=0)
    document.configure_plotter(pc3)
    document.plot_pdf(output, Rect(Point(1, 2), Point(301, 202)), 0, ())
    assert calls == [str(pc3.resolve())]
    assert raw.ActiveLayout.ConfigName == "DWG To PDF.pc3"


def test_plot_waits_for_cad_idle_before_restoring_background(tmp_path, monkeypatch):
    busy = [True]
    queries = []
    writes = []
    plots = []
    def state():
        queries.append(True)
        if len(queries) == 3:
            busy[0] = False
        return SimpleNamespace(IsQuiescent=not busy[0])
    def write(name, value):
        if value == 2 and busy[0]:
            raise RuntimeError("CAD rejected restore while plotting")
        writes.append(value)
    def plot(path):
        plots.append(path)
        pdf(Path(path))
        return True
    raw = SimpleNamespace(ActiveLayout=Layout(), GetVariable=lambda name: 2,
        SetVariable=write, Plot=SimpleNamespace(PlotToFile=plot),
        Application=SimpleNamespace(GetAcadState=state))
    output = tmp_path / "busy.pdf"
    plot_pdf(raw, output, Rect(Point(1, 2), Point(301, 202)), 0, ())
    assert len(queries) == 3
    assert writes == [0, 2]
    assert len(plots) == 1
    validate_orientation(output)


@pytest.mark.parametrize("hresult", [-2147418111, -2147417846])
def test_post_plot_wait_retries_only_busy_reads(monkeypatch, hresult):
    import pywintypes
    from dwg_to_pdf.autocad import readiness as plotting
    calls = []
    def state():
        calls.append(True)
        if len(calls) == 1:
            raise pywintypes.com_error(hresult, "busy", None, None)
        return SimpleNamespace(IsQuiescent=True)
    raw = SimpleNamespace(Application=SimpleNamespace(GetAcadState=state))
    monkeypatch.setattr(plotting.time, "sleep", lambda seconds: None)
    plotting.wait_for_document_ready(raw)
    assert len(calls) == 2


def test_post_plot_wait_propagates_non_busy_error(monkeypatch):
    import pywintypes
    from dwg_to_pdf.autocad import readiness as plotting
    def state():
        raise pywintypes.com_error(-1, "fatal", None, None)
    monkeypatch.setattr(plotting.time, "sleep", lambda seconds: pytest.fail("must not retry"))
    with pytest.raises(pywintypes.com_error):
        plotting.wait_for_document_ready(SimpleNamespace(Application=SimpleNamespace(GetAcadState=state)))


def test_post_plot_timeout_does_not_restore_or_repeat_plot(tmp_path, monkeypatch):
    from dwg_to_pdf.autocad import readiness as plotting
    clock = iter([0., 31.])
    writes, plots = [], []
    def plot(path):
        plots.append(path)
        pdf(Path(path))
        return True
    raw = SimpleNamespace(ActiveLayout=Layout(), GetVariable=lambda name: 2,
        SetVariable=lambda name, value: writes.append(value),
        Plot=SimpleNamespace(PlotToFile=plot),
        Application=SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=False)))
    monkeypatch.setattr(plotting.time, "monotonic", lambda: next(clock))
    output = tmp_path / "timeout.pdf"
    with pytest.raises(AppError) as error:
        plot_pdf(raw, output, Rect(Point(1, 2), Point(301, 202)), 0, ())
    assert error.value.code == "E410"
    assert writes == [0]
    assert len(plots) == 1
    assert not output.exists()


@pytest.mark.parametrize("hresult", [-2147418111, -2147417846])
def test_readiness_handles_busy_metadata_hidden_by_pywin32(monkeypatch, hresult):
    import pywintypes
    from win32com.client.dynamic import CDispatch
    from win32com.client.build import DispatchItem
    from dwg_to_pdf.autocad import readiness
    calls = []
    application = SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=True))
    class Ole:
        def GetIDsOfNames(self, locale, name):
            calls.append(name)
            if len(calls) == 1:
                raise pywintypes.com_error(hresult, "busy metadata", None, None)
            return 1
        def Invoke(self, *args): return application
    raw = CDispatch(Ole(), DispatchItem(), "Open")
    monkeypatch.setattr(readiness.time, "sleep", lambda seconds: None)
    readiness.wait_for_document_ready(raw)
    assert calls == ["Application", "Application"]


def test_plot_retries_metadata_read_then_restores_once(tmp_path, monkeypatch):
    from dwg_to_pdf.autocad import readiness
    queries, writes, plots = [], [], []
    class Raw:
        ActiveLayout = Layout()
        @property
        def Application(self):
            queries.append(True)
            if len(queries) == 1:
                raise AttributeError("Open.Application")
            return SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=True))
        def GetVariable(self, name): return 2
        def SetVariable(self, name, value): writes.append(value)
        @property
        def Plot(self): return SimpleNamespace(PlotToFile=plot)
    def plot(path):
        plots.append(path)
        pdf(Path(path))
        return True
    monkeypatch.setattr(readiness.time, "sleep", lambda seconds: None)
    output = tmp_path / "metadata.pdf"
    plot_pdf(Raw(), output, Rect(Point(1, 2), Point(301, 202)), 0, ())
    assert len(queries) == 3  # Two readiness reads, then the existing version query.
    assert writes == [0, 2]
    assert len(plots) == 1
    validate_orientation(output)


def test_persistent_metadata_error_keeps_timeout_and_never_retries_mutations(tmp_path, monkeypatch):
    from dwg_to_pdf.autocad import readiness
    clock = iter([0., 31.])
    writes, plots = [], []
    class Raw:
        ActiveLayout = Layout()
        @property
        def Application(self): raise AttributeError("Open.Application")
        def GetVariable(self, name): return 2
        def SetVariable(self, name, value): writes.append(value)
        @property
        def Plot(self): return SimpleNamespace(PlotToFile=plot)
    def plot(path):
        plots.append(path)
        pdf(Path(path))
        return True
    monkeypatch.setattr(readiness.time, "monotonic", lambda: next(clock))
    output = tmp_path / "metadata-timeout.pdf"
    with pytest.raises(AppError) as error:
        plot_pdf(Raw(), output, Rect(Point(1, 2), Point(301, 202)), 0, ())
    assert error.value.code == "E410"
    assert "30 seconds" in str(error.value.__cause__.__cause__)
    assert writes == [0]
    assert len(plots) == 1
    assert not output.exists()
