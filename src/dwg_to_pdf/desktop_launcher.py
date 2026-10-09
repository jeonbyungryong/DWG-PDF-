from __future__ import annotations

from collections.abc import Callable, Sequence
import ctypes
import base64
import json
import sys
import subprocess
from typing import Protocol
from .cad.discovery import discover_candidates
from .cad.selection import CadCandidate, CadSelection, ProviderId, select_candidate
from .cad.factory import EXPERIMENTAL_WARNING
from .errors import AppError
from .windows_picker import pick_dwg_files, pick_folder, pick_config_file


class DesktopUI(Protocol):
    def choose_cad_provider(self) -> ProviderId | None: ...
    def choose_cad_candidate(self, candidates: tuple[CadCandidate, ...]) -> str | None: ...
    def choose_autocad_config(self) -> str: ...
    def confirm_experimental_autocad(self) -> bool: ...
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

    def choose_cad_provider(self) -> ProviderId | None:
        answer = _message_box("CAD 선택", "예: GstarCAD (기본)\n아니요: AutoCAD (실험적)\n취소: 종료", 0x23)
        return {6: "gstarcad", 7: "autocad"}.get(answer)

    def confirm_experimental_autocad(self) -> bool:
        return _message_box("AutoCAD 실험적 지원", EXPERIMENTAL_WARNING + "\n계속하시겠습니까?", 0x134) == 6

    def choose_autocad_config(self) -> str:
        return pick_config_file("AutoCAD 용지·플로터 설정 TOML 선택")

    def choose_cad_candidate(self, candidates: tuple[CadCandidate, ...]) -> str | None:
        if len(candidates) == 1:
            candidate = candidates[0]
            answer = _message_box("CAD 설치 선택", f"{candidate.product_name}\n{candidate.prog_id}\n{candidate.executable}\n사용하시겠습니까?", 0x21)
            return candidate.prog_id if answer == 1 else None
        data = [f"{item.product_name} | {item.prog_id} | {item.executable}" for item in candidates]
        encoded = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("ascii")
        selected = _run_picker(
            "$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
            "Add-Type -AssemblyName System.Windows.Forms;"
            f"$items=ConvertFrom-Json ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')));"
            "$f=New-Object Windows.Forms.Form;$f.Text='CAD 선택';$f.Width=820;$f.Height=260;"
            "$list=New-Object Windows.Forms.ListBox;$list.Dock='Top';$list.Height=160;"
            "$items|ForEach-Object{[void]$list.Items.Add([string]$_)};"
            "$ok=New-Object Windows.Forms.Button;$ok.Text='OK';$ok.Dock='Bottom';"
            "$ok.Add_Click({if($list.SelectedIndex -ge 0){$f.DialogResult='OK';$f.Close()}});"
            "$f.Controls.Add($list);$f.Controls.Add($ok);"
            "if($f.ShowDialog() -eq 'OK'){Write-Output $list.SelectedIndex};$f.Dispose()"
        )
        if len(selected) == 1 and selected[0].isdigit():
            index = int(selected[0])
            if 0 <= index < len(candidates):
                return candidates[index].prog_id
        return None

    def choose_source_mode(self) -> str | None:
        answer = _message_box(
            "DWG to PDF",
            "입력 방식을 선택하십시오.\n\n예: DWG 파일 여러 개 선택\n아니요: DWG 폴더 선택\n취소: 종료",
            0x00000003 | 0x00000020,
        )
        return {6: "files", 7: "folder"}.get(answer)

    def choose_files(self) -> Sequence[str]:
        return pick_dwg_files("변환할 DWG 파일 선택")

    def choose_input_folder(self) -> str:
        return self._choose_folder("DWG 입력 폴더 선택")

    def choose_output_folder(self) -> str:
        return self._choose_folder("PDF 출력 폴더 선택")

    @staticmethod
    def _choose_folder(title: str) -> str:
        return pick_folder(title)

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
        provider = desktop.choose_cad_provider()
        if provider is None:
            return 0
        experimental = provider == "autocad"
        if experimental and not desktop.confirm_experimental_autocad():
            return 0
        candidates = discover_candidates(provider)
        # Validate conflicting registrations before showing one entry per installation.
        if candidates:
            select_candidate(CadSelection(provider, candidates[0].prog_id, experimental), candidates)
        else:
            select_candidate(CadSelection(provider, None, experimental), candidates)
        unique = {}
        for candidate in sorted(candidates, key=lambda item: item.prog_id.count("."), reverse=True):
            unique.setdefault((candidate.clsid.casefold(), str(candidate.executable).casefold()), candidate)
        selected = desktop.choose_cad_candidate(tuple(unique.values()))
        if selected is None:
            return 0
        arguments = [*sources, "--output", output, "--conflict", "copy", "--cad", provider, "--cad-prog-id", selected]
        if experimental:
            arguments.append("--allow-experimental-autocad")
            config = desktop.choose_autocad_config()
            if not config:
                return 0
            arguments.extend(["--config", config])
        exit_code = run_cli(arguments)
        desktop.show_result(exit_code)
        return exit_code
    except (AppError, OSError, ValueError) as error:
        print(f"CAD 선택 실패: {error}", file=sys.stderr)
        desktop.show_result(2)
        return 2
    finally:
        desktop.close()
