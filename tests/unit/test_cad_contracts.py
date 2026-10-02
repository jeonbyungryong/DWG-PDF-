from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from dwg_to_pdf.configuration import AppConfig
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.domain import FrameCandidate, MatchDecision, Point, Rect, ScaleRatio
from dwg_to_pdf.errors import AppError


class ContractDocument:
    def __init__(self, fail=False):
        self.enabled = None
        self.calls = []
        self.fail = fail

    @property
    def raw(self):
        raise AssertionError("provider-neutral service must not access raw COM")

    def configure_extraction(self, enabled):
        self.enabled = enabled

    def plot_pdf(self, output, window, rotation, preferred_media_names):
        self.calls.append((output, window, rotation, preferred_media_names))
        if self.fail:
            output.write_bytes(b"partial")
            raise AppError("E410", "synthetic plot failure")
        writer = PdfWriter()
        page = writer.add_blank_page(width=297 * 72 / 25.4, height=210 * 72 / 25.4)
        stream = DecodedStreamObject()
        stream.set_data(b"0 0 0 RG 5 w 20 20 m 400 300 l S")
        page[NameObject("/Contents")] = writer._add_object(stream)
        with output.open("wb") as target:
            writer.write(target)


@contextmanager
def working_document(document, workspace):
    assert workspace.authorized_copy().is_file()
    yield document


@pytest.fixture
def conversion_case(tmp_path, monkeypatch):
    source = tmp_path / "sample.dwg"
    source.write_bytes(b"unchanged-source")
    output = tmp_path / "pdf"
    output.mkdir()
    window = Rect(Point(1, 2), Point(420, 297))
    candidate = FrameCandidate("p", SimpleNamespace(), 90, window, window, 0)
    profile = SimpleNamespace(profile_id="p", scale=ScaleRatio(1, 1))
    config = AppConfig("GStarCAD.Application.26", True, "DWG To PDF.pc3", 297, 210,
                       "monochrome.ctb", ("User77",), .8, .1)
    service = ConversionService(config, SimpleNamespace(all=lambda: (profile,)))
    monkeypatch.setattr("dwg_to_pdf.conversion_service.require_stable", lambda path: None)
    monkeypatch.setattr("dwg_to_pdf.conversion_service.detect_scale_cell", lambda *args: object())
    monkeypatch.setattr("dwg_to_pdf.conversion_service.profiles_for_scale_cell", lambda *args: (profile,))
    monkeypatch.setattr("dwg_to_pdf.conversion_service.choose_profile_by_structure", lambda *args: MatchDecision(candidate, .9, .2))
    return service, source, output, window


def test_provider_independent_service_never_reads_raw(conversion_case):
    service, source, output, window = conversion_case
    doc = ContractDocument()
    session = SimpleNamespace(working_document=lambda workspace: working_document(doc, workspace))
    outcome = service.convert_in_session(session, source, output, "copy")
    assert doc.enabled is True
    assert doc.calls[0][1:] == (window, 90, ("User77",))
    assert outcome.frames[0].scale == ScaleRatio(1, 1)
    assert outcome.frames[0].output.is_file()
    assert source.read_bytes() == b"unchanged-source"
    assert not list(output.glob("*.tmp.pdf"))


def test_failed_plot_never_publishes_pdf(conversion_case):
    service, source, output, window = conversion_case
    doc = ContractDocument(fail=True)
    session = SimpleNamespace(working_document=lambda workspace: working_document(doc, workspace))
    with pytest.raises(AppError) as error:
        service.convert_in_session(session, source, output, "copy")
    assert error.value.code == "E410"
    assert list(output.iterdir()) == []
    assert source.read_bytes() == b"unchanged-source"


def test_conversion_emits_stage_and_failure_code_without_private_paths(conversion_case, capsys):
    import json
    from dwg_to_pdf.cad.diagnostics import diagnostic_scope
    from dwg_to_pdf.cad.selection import CadCandidate
    service, source, output, _ = conversion_case
    doc = ContractDocument(fail=True)
    session = SimpleNamespace(working_document=lambda workspace: working_document(doc, workspace))
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    with diagnostic_scope(candidate, "test"), pytest.raises(AppError):
        service.convert_in_session(session, source, output, "copy")
    lines = capsys.readouterr().err.splitlines()
    records = [json.loads(line.removeprefix("CAD_DIAGNOSTIC ")) for line in lines]
    assert [record["stage"] for record in records] == ["open", "detect", "plot", "plot"]
    assert records[-1]["code"] == "E410"
    assert str(source) not in " ".join(lines)
