from types import SimpleNamespace

import pytest

from dwg_to_pdf.errors import AppError
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


def test_gstar_prepares_colors_before_any_plot_configuration(monkeypatch, tmp_path):
    raw, colored = raw_document()
    events = []

    def environment(layout, names):
        assert colored.Color == 7
        events.append("environment")
        return "A4"

    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.require_plot_environment", environment)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.apply_plot_settings", lambda *a: events.append("settings"))
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.plot_to_file", lambda *a: events.append("plot"))
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.normalize_portrait_plot", lambda *a: events.append("normalize"))
    GstarDocument(raw).plot_pdf(tmp_path / "out.pdf", (0, 0, 1, 1), 0, ())
    assert events == ["environment", "settings", "plot", "normalize"]


@pytest.mark.parametrize("document_type", [GstarDocument, AutoCADDocument])
def test_preparation_failure_does_not_configure_or_plot(monkeypatch, tmp_path, document_type):
    raw, colored = raw_document()
    raw.Blocks = Collection([SimpleNamespace(IsXRef=True)])
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.require_plot_environment", lambda *a: pytest.fail("plot settings touched"))
    monkeypatch.setattr("dwg_to_pdf.autocad.plotting.plot_pdf", lambda *a, **k: pytest.fail("plot touched"))
    with pytest.raises(AppError) as error:
        document_type(raw).plot_pdf(tmp_path / "out.pdf", (0, 0, 1, 1), 0, ())
    assert error.value.code == "E410"
    assert colored.Color == 256
    assert not (tmp_path / "out.pdf").exists()


@pytest.mark.parametrize("document_type", [GstarDocument, AutoCADDocument])
def test_each_adapter_calls_shared_preparation_exactly_once(monkeypatch, tmp_path, document_type):
    from dwg_to_pdf.cad.monochrome import prepare_monochrome
    from dwg_to_pdf.autocad.monochrome import prepare_monochrome as compatible
    assert compatible is prepare_monochrome
    raw, colored = raw_document()
    calls = []

    def prepare(document):
        calls.append(document)
        prepare_monochrome(document)

    def plot(*a, **k):
        assert calls == [raw]
        assert colored.Color == 7

    monkeypatch.setattr("dwg_to_pdf.cad.monochrome.prepare_monochrome", prepare)
    monkeypatch.setattr("dwg_to_pdf.autocad.plotting.plot_pdf", plot)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.require_plot_environment", lambda *a: "A4")
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.apply_plot_settings", lambda *a: None)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.plot_to_file", plot)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.normalize_portrait_plot", lambda *a: None)
    document_type(raw).plot_pdf(tmp_path / "out.pdf", (0, 0, 1, 1), 0, ())
    assert calls == [raw]
