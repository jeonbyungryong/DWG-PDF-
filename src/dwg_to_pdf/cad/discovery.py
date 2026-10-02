"""Read-only COM registration discovery; never starts a COM server.

Registration and executable metadata are discovery evidence, not license or
runtime compatibility evidence. Ownership must be re-proven when launching.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import uuid
import winreg

from ..errors import AppError
from .selection import CadCandidate, ProviderId


@dataclass(frozen=True)
class Registration:
    prog_id: str
    clsid: str
    command: str
    server_executable: str | None


def _value(hive: int, key: str, name: str | None = None) -> str | None:
    try:
        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as handle:
            value, kind = winreg.QueryValueEx(handle, name)
    except FileNotFoundError:
        return None
    if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(value, str):
        raise AppError("E202", "CAD discovery: registry value is not a string")
    return os.path.expandvars(value) if kind == winreg.REG_EXPAND_SZ else value


def _read_registrations(provider: ProviderId) -> tuple[Registration, ...]:
    prefix = "GStarCAD.Application" if provider == "gstarcad" else "AutoCAD.Application"
    records: list[Registration] = []
    base = r"Software\Classes"
    try:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, base, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as root:
                    names = [winreg.EnumKey(root, index) for index in range(winreg.QueryInfoKey(root)[0])]
            except FileNotFoundError:
                continue
            for name in names:
                if not re.fullmatch(re.escape(prefix) + r"(?:\.[0-9]+)*", name, re.IGNORECASE):
                    continue
                clsid = _value(hive, base + "\\" + name + r"\CLSID")
                if not clsid:
                    raise AppError("E202", f"{provider}: ProgID has no CLSID")
                try:
                    uuid.UUID(clsid.strip("{}"))
                except ValueError as error:
                    raise AppError("E202", f"{provider}: invalid CLSID") from error
                clskey = base + "\\CLSID\\" + clsid
                if _value(hive, clskey, "LocalService"):
                    raise AppError("E202", f"{provider}: service-hosted COM server is not supported")
                serverkey = clskey + r"\LocalServer32"
                command = _value(hive, serverkey)
                if not command:
                    raise AppError("E202", f"{provider}: missing local executable registration")
                records.append(Registration(name, clsid, command, _value(hive, serverkey, "ServerExecutable")))
    except AppError:
        raise
    except OSError as error:
        raise AppError("E202", f"{provider}: cannot read CAD registration") from error
    return tuple(records)


def _server_executable(command: str, server_executable: str | None) -> Path:
    if not isinstance(command, str) or any(ord(char) < 32 for char in command):
        raise AppError("E202", "CAD discovery: invalid server command")
    if server_executable is not None:
        path_text = server_executable
    elif command.startswith('"'):
        match = re.match(r'^"([^"\r\n]+\.exe)"(?:\s|$)', command, re.IGNORECASE)
        if not match:
            raise AppError("E202", "CAD discovery: malformed quoted executable")
        path_text = match.group(1)
    else:
        match = re.match(r'^(.+?\.exe)(?:\s|$)', command, re.IGNORECASE)
        if not match:
            raise AppError("E202", "CAD discovery: missing executable path")
        path_text = match.group(1)
        # CreateProcess may try earlier whitespace-delimited executable prefixes.
        for whitespace in re.finditer(r"\s+", path_text):
            if Path(path_text[:whitespace.start()] + ".exe").is_file():
                raise AppError("E202", "CAD discovery: ambiguous unquoted executable path")
    path = Path(path_text)
    if not path.is_absolute() or path.suffix.casefold() != ".exe" or '"' in path_text:
        raise AppError("E202", "CAD discovery: server executable must be an absolute EXE path")
    try:
        path = path.resolve(strict=True)
        if not path.is_file():
            raise OSError("not a file")
    except OSError as error:
        raise AppError("E202", "CAD discovery: registered executable does not exist") from error
    return path


def _file_identity(path: Path) -> tuple[str, str | None]:
    import pywintypes  # Bootstrap pywin32 DLL discovery even before any COM import.
    import win32api
    try:
        translations = win32api.GetFileVersionInfo(str(path), r"\VarFileInfo\Translation")
        products = set()
        versions = set()
        for language, codepage in translations:
            prefix = f"\\StringFileInfo\\{language:04x}{codepage:04x}\\"
            products.add(str(win32api.GetFileVersionInfo(str(path), prefix + "ProductName")).strip())
            versions.add(str(win32api.GetFileVersionInfo(str(path), prefix + "ProductVersion")).strip())
        if len(products) != 1:
            raise ValueError("inconsistent product metadata")
        return products.pop(), next(iter(versions)) if len(versions) == 1 else None
    except Exception as error:
        raise AppError("E223", "CAD discovery: executable product identity unavailable") from error


def _launch_arguments(command: str, executable: Path) -> tuple[str, ...]:
    """Parse data with Windows argv rules, never execute the registry command."""
    pattern = r'^"([^"\r\n]+\.exe)"(.*)$' if command.startswith('"') else r'^(.+?\.exe)(?:\s(.*)|$)'
    match = re.match(pattern, command, re.IGNORECASE)
    if not match or len(command) > 32768 or Path(match.group(1)).resolve() != executable:
        raise AppError("E202", "CAD discovery: command and ServerExecutable disagree")
    tail = match.group(2) or ""
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    split = shell.CommandLineToArgvW
    split.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    split.restype = ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    argv = split("placeholder.exe " + tail, ctypes.byref(count))
    if not argv:
        raise AppError("E202", "CAD discovery: cannot parse launch arguments")
    try:
        return tuple(argv[index].casefold() for index in range(1, count.value))
    finally:
        free = ctypes.WinDLL("kernel32").LocalFree
        free.argtypes = [wintypes.HLOCAL]
        free.restype = wintypes.HLOCAL
        free(ctypes.cast(argv, wintypes.HLOCAL))


def _require_standard_autocad_mode(arguments: tuple[str, ...]) -> None:
    index = 0
    seen = set()
    while index < len(arguments):
        flag = arguments[index]
        if flag in seen:
            raise AppError("E223", "autocad: repeated launch mode is ambiguous")
        seen.add(flag)
        if flag in ("/automation", "-automation", "/embedding", "-embedding", "/nologo"):
            index += 1
        elif flag in ("/product", "/language") and index + 1 < len(arguments):
            value = arguments[index + 1]
            if (flag == "/product" and value != "acad") or (flag == "/language" and not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", value)):
                raise AppError("E223", "autocad: excluded or unidentified product launch mode")
            index += 2
        else:
            raise AppError("E223", "autocad: unverified launch arguments; standard product mode required")


def discover_candidates(provider: ProviderId) -> tuple[CadCandidate, ...]:
    if provider not in ("gstarcad", "autocad"):
        raise AppError("E001", "invalid CAD provider")
    candidates: dict[str, CadCandidate] = {}
    registrations = []
    by_progid, by_clsid = {}, {}
    for record in _read_registrations(provider):
        executable = _server_executable(record.command, record.server_executable)
        arguments = _launch_arguments(record.command, executable)
        identity = (str(executable).casefold(), arguments)
        progid_key, clsid_key = record.prog_id.casefold(), record.clsid.casefold()
        if (progid_key in by_progid and by_progid[progid_key] != (clsid_key, identity)
                or clsid_key in by_clsid and by_clsid[clsid_key] != identity):
            raise AppError("E202", f"{provider}: conflicting executable or launch-mode registrations")
        by_progid[progid_key], by_clsid[clsid_key] = (clsid_key, identity), identity
        registrations.append((record, executable, arguments))
    for record, executable, arguments in registrations:
        if provider == "autocad":
            _require_standard_autocad_mode(arguments)
        product, version = _file_identity(executable)
        approved_name = r"(?:Autodesk\s+)?AutoCAD(?:\s+20[0-9]{2})?" if provider == "autocad" else r"GstarCAD(?:\s*20[0-9]{2})?(?:\s+(?:Standard|Professional))?"
        expected_exe = "acad.exe" if provider == "autocad" else "gcad.exe"
        if not re.fullmatch(approved_name, product, re.IGNORECASE) or executable.name.casefold() != expected_exe:
            raise AppError("E223", f"{provider}: LT, vertical, or unidentified product is excluded")
        candidate = CadCandidate(provider, record.prog_id, record.clsid, executable, product, version, arguments)
        key = record.prog_id.casefold()
        prior = candidates.get(key)
        if prior and (prior.clsid.casefold(), str(prior.executable).casefold()) != (record.clsid.casefold(), str(executable).casefold()):
            raise AppError("E202", f"{provider}: conflicting CAD registrations")
        candidates[key] = candidate
    return tuple(sorted(candidates.values(), key=lambda item: item.prog_id.casefold()))
