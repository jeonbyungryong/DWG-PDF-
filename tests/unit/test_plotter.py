from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.plotter import _wait_for_stable_pdf, plot_to_file


class FakeDocument:
    def __init__(self, output: Path, result=True, error: Exception | None = None) -> None:
        self.output = output
        self.result = result
        self.error = error
        self.variables = {"BACKGROUNDPLOT": 3}
        self.calls: list[tuple[str, object]] = []
        self.Plot = SimpleNamespace(PlotToFile=self._plot)

    def GetVariable(self, name: str):
        self.calls.append(("get", name))
        return self.variables[name]

    def SetVariable(self, name: str, value: object) -> None:
        self.calls.append(("set", (name, value)))
        self.variables[name] = value

    def _plot(self, output: str):
        self.calls.append(("plot", output))
        if self.error:
            raise self.error
        if self.result:
            Path(output).write_bytes(b"%PDF-" + b"x" * 200)
        return self.result


def test_plot_to_file_disables_background_and_restores_it(tmp_path: Path) -> None:
    output = tmp_path / "out.pdf"
    document = FakeDocument(output)
    plot_to_file(document, output, stability_checks=1, stability_interval_sec=0)
    assert document.variables["BACKGROUNDPLOT"] == 3
    assert document.calls[1] == ("set", ("BACKGROUNDPLOT", 0))
    assert document.calls[-1] == ("set", ("BACKGROUNDPLOT", 3))


@pytest.mark.parametrize("mode", ["false", "missing", "zero", "exception"])
def test_plot_failures_are_stable_app_errors_and_restore_background(tmp_path: Path, mode: str) -> None:
    output = tmp_path / "out.pdf"
    document = FakeDocument(
        output,
        result=mode not in {"false", "missing"},
        error=RuntimeError("raw COM details") if mode == "exception" else None,
    )
    if mode == "missing":
        document._plot = lambda output: True
        document.Plot.PlotToFile = document._plot
    elif mode == "zero":
        document._plot = lambda output: Path(output).write_bytes(b"") or True
        document.Plot.PlotToFile = document._plot

    with pytest.raises(AppError) as raised:
        plot_to_file(document, output, stability_checks=1, stability_interval_sec=0)
    assert raised.value.code == "E410"
    assert "raw COM details" not in str(raised.value)
    assert document.variables["BACKGROUNDPLOT"] == 3
    assert not output.exists()


def test_changing_pdf_never_becomes_stable_without_sleep(tmp_path: Path) -> None:
    output = tmp_path / "changing.pdf"
    output.write_bytes(b"%PDF-" + b"x" * 200)
    values = iter(SimpleNamespace(st_size=200, st_mtime_ns=index) for index in range(20))
    sleeps: list[float] = []

    with pytest.raises(AppError) as raised:
        _wait_for_stable_pdf(
            output,
            checks=3,
            interval_sec=0.25,
            stat=lambda path: next(values),
            sleep=sleeps.append,
        )

    assert raised.value.code == "E410"
    assert sleeps


@pytest.mark.parametrize("failure", ["resolve", "exists", "mkdir"])
def test_plot_filesystem_failures_are_wrapped(tmp_path: Path, monkeypatch, failure: str) -> None:
    output = tmp_path / "out.pdf"
    if failure == "resolve":
        monkeypatch.setattr(
            "dwg_to_pdf.gstarcad.plotter._resolve_path",
            lambda path: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )
    elif failure == "exists":
        monkeypatch.setattr(
            "dwg_to_pdf.gstarcad.plotter._path_exists",
            lambda path: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )
    else:
        monkeypatch.setattr(
            "dwg_to_pdf.gstarcad.plotter._make_dir",
            lambda path: (_ for _ in ()).throw(PermissionError("denied")),
            raising=False,
        )

    with pytest.raises(AppError) as raised:
        plot_to_file(FakeDocument(output), output, stability_checks=1, stability_interval_sec=0)
    assert raised.value.code == "E410"


def test_plot_rejects_existing_output_and_non_pdf_suffix(tmp_path: Path) -> None:
    output = tmp_path / "out.pdf"
    output.write_bytes(b"existing")
    with pytest.raises(AppError):
        plot_to_file(FakeDocument(output), output)
    with pytest.raises(AppError):
        plot_to_file(FakeDocument(tmp_path / "out.txt"), tmp_path / "out.txt")


def test_arbitrary_com_exception_is_wrapped_and_partial_is_removed(tmp_path: Path) -> None:
    output = tmp_path / "out.pdf"

    class ComFailure(Exception):
        pass

    document = FakeDocument(output, error=ComFailure("raw COM details"))
    with pytest.raises(AppError) as raised:
        plot_to_file(document, output, stability_checks=1, stability_interval_sec=0)
    assert raised.value.code == "E410"
    assert "raw COM details" not in str(raised.value)
    assert not output.exists()
