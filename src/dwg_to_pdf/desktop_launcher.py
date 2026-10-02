from __future__ import annotations

from collections.abc import Callable, Sequence
import ctypes
import subprocess
from typing import Protocol


class DesktopUI(Protocol):
    def choose_source_mode(self) -> str | None: ...
    def choose_files(self) -> Sequence[str]: ...
    def choose_input_folder(self) -> str: ...
    def choose_output_folder(self) -> str: ...
    def show_result(self, exit_code: int) -> None: ...
    def close(self) -> None: ...


def _message_box(title: str, message: str, flags: int) -> int:
    return int(ctypes.windll.user32.MessageBoxW(None, message, title, flags))


def _run_picker(script: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        return ()
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


class WindowsDesktopUI:
    """Dependency-free Windows launcher used when the EXE is double-clicked."""

    def choose_source_mode(self) -> str | None:
        answer = _message_box(
            "DWG to PDF",
            "입력 방식을 선택하십시오.\n\n예: DWG 파일 여러 개 선택\n아니요: DWG 폴더 선택\n취소: 종료",
            0x00000003 | 0x00000020,
        )
        return {6: "files", 7: "folder"}.get(answer)

    def choose_files(self) -> Sequence[str]:
        return _run_picker(
            "$ErrorActionPreference='Stop';"
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d=New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title='변환할 DWG 파일 선택';$d.Filter='DWG 도면 (*.dwg)|*.dwg';"
            "$d.Multiselect=$true;"
            "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$d.FileNames|ForEach-Object{Write-Output $_}};"
            "$d.Dispose()"
        )

    def choose_input_folder(self) -> str:
        return self._choose_folder("DWG 입력 폴더 선택")

    def choose_output_folder(self) -> str:
        return self._choose_folder("PDF 출력 폴더 선택")

    @staticmethod
    def _choose_folder(title: str) -> str:
        safe_title = title.replace("'", "''")
        selected = _run_picker(
            "$ErrorActionPreference='Stop';"
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
            f"$d.Description='{safe_title}';$d.ShowNewFolderButton=$true;"
            "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){Write-Output $d.SelectedPath};"
            "$d.Dispose()"
        )
        return selected[0] if selected else ""

    def show_result(self, exit_code: int) -> None:
        if exit_code == 0:
            _message_box("DWG to PDF", "PDF 변환 작업이 완료되었습니다.", 0x00000040)
        elif exit_code == 1:
            _message_box(
                "DWG to PDF",
                "작업은 완료되었으나 실패 또는 건너뛴 도면이 있습니다. 콘솔의 결과 보고를 확인하십시오.",
                0x00000030,
            )
        else:
            _message_box(
                "DWG to PDF",
                "변환을 시작하지 못했습니다. 콘솔의 오류 내용을 확인하십시오.",
                0x00000010,
            )

    def close(self) -> None:
        return None


def run_desktop(
    run_cli: Callable[[list[str]], int],
    *,
    ui: DesktopUI | None = None,
) -> int:
    """Collect desktop selections and delegate to the tested CLI conversion path."""

    desktop = ui if ui is not None else WindowsDesktopUI()
    try:
        mode = desktop.choose_source_mode()
        if mode is None:
            return 0
        if mode == "files":
            sources = list(desktop.choose_files())
        elif mode == "folder":
            folder = desktop.choose_input_folder()
            sources = [folder] if folder else []
        else:
            return 0
        if not sources:
            return 0
        output = desktop.choose_output_folder()
        if not output:
            return 0
        exit_code = run_cli([*sources, "--output", output, "--conflict", "copy"])
        desktop.show_result(exit_code)
        return exit_code
    finally:
        desktop.close()
