from __future__ import annotations

from types import SimpleNamespace


class FakeUI:
    def __init__(
        self,
        *,
        mode: str | None,
        files: tuple[str, ...] = (),
        input_folder: str = "",
        output_folder: str = "",
    ) -> None:
        self.mode = mode
        self.files = files
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.result: int | None = None
        self.closed = False

    def choose_source_mode(self) -> str | None:
        return self.mode

    def choose_files(self) -> tuple[str, ...]:
        return self.files

    def choose_input_folder(self) -> str:
        return self.input_folder

    def choose_output_folder(self) -> str:
        return self.output_folder

    def show_result(self, exit_code: int) -> None:
        self.result = exit_code

    def close(self) -> None:
        self.closed = True


def test_file_selection_runs_existing_cli_contract() -> None:
    from dwg_to_pdf.desktop_launcher import run_desktop

    ui = FakeUI(
        mode="files",
        files=(r"D:\input\a.dwg", r"D:\input\b.dwg"),
        output_folder=r"D:\output",
    )
    received: list[list[str]] = []

    exit_code = run_desktop(lambda args: received.append(args) or 0, ui=ui)

    assert exit_code == 0
    assert received == [[
        r"D:\input\a.dwg",
        r"D:\input\b.dwg",
        "--output",
        r"D:\output",
        "--conflict",
        "copy",
    ]]
    assert ui.result == 0
    assert ui.closed is True


def test_folder_selection_runs_existing_cli_contract() -> None:
    from dwg_to_pdf.desktop_launcher import run_desktop

    ui = FakeUI(mode="folder", input_folder=r"D:\input", output_folder=r"D:\output")
    received: list[list[str]] = []

    exit_code = run_desktop(lambda args: received.append(args) or 1, ui=ui)

    assert exit_code == 1
    assert received == [[r"D:\input", "--output", r"D:\output", "--conflict", "copy"]]
    assert ui.result == 1
    assert ui.closed is True


def test_cancel_does_not_start_conversion_and_closes_ui() -> None:
    from dwg_to_pdf.desktop_launcher import run_desktop

    ui = FakeUI(mode=None)
    called = False

    def runner(_args: list[str]) -> int:
        nonlocal called
        called = True
        return 0

    assert run_desktop(runner, ui=ui) == 0
    assert called is False
    assert ui.result is None
    assert ui.closed is True


def test_cancelled_source_or_output_selection_never_starts_conversion() -> None:
    from dwg_to_pdf.desktop_launcher import run_desktop

    cases = (
        FakeUI(mode="files", files=(), output_folder=r"D:\output"),
        FakeUI(mode="folder", input_folder="", output_folder=r"D:\output"),
        FakeUI(mode="folder", input_folder=r"D:\input", output_folder=""),
    )
    for ui in cases:
        assert run_desktop(lambda _args: (_ for _ in ()).throw(AssertionError("must not run")), ui=ui) == 0
        assert ui.closed is True


def test_windows_source_mode_maps_native_yes_no_cancel(monkeypatch) -> None:
    from dwg_to_pdf import desktop_launcher

    ui = desktop_launcher.WindowsDesktopUI()
    for native_result, expected in ((6, "files"), (7, "folder"), (2, None)):
        monkeypatch.setattr(desktop_launcher, "_message_box", lambda *_args, value=native_result: value)
        assert ui.choose_source_mode() == expected


def test_windows_file_picker_returns_utf8_paths_without_tk(monkeypatch) -> None:
    from dwg_to_pdf import desktop_launcher

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert kwargs["encoding"] == "utf-8"
        return SimpleNamespace(returncode=0, stdout="D:/도면/a.dwg\nD:/도면/b.dwg\n", stderr="")

    monkeypatch.setattr(desktop_launcher.subprocess, "run", fake_run)

    assert desktop_launcher.WindowsDesktopUI().choose_files() == ("D:/도면/a.dwg", "D:/도면/b.dwg")
    assert calls[0][:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA"]


def test_windows_folder_picker_returns_selected_path(monkeypatch) -> None:
    from dwg_to_pdf import desktop_launcher

    monkeypatch.setattr(
        desktop_launcher.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="D:/PDF 출력\n", stderr=""),
    )
    ui = desktop_launcher.WindowsDesktopUI()

    assert ui.choose_input_folder() == "D:/PDF 출력"
    assert ui.choose_output_folder() == "D:/PDF 출력"
