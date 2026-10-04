from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import json

import pytest

from dwg_to_pdf.cad import discovery
from dwg_to_pdf.errors import AppError


@pytest.fixture
def registered(tmp_path, monkeypatch):
    exe = tmp_path / "CAD folder" / "acad.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"synthetic executable metadata only; never run")
    raw = discovery.Registration("AutoCAD.Application.25", "{00000000-0000-0000-0000-000000000025}",
                                 f'"{exe}" /Automation', None)
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: (raw,))
    monkeypatch.setattr(discovery, "_file_identity", lambda path: ("AutoCAD", "25.0"))
    return exe, raw


def test_discovery_never_dispatches_or_writes_registry(registered, monkeypatch):
    import win32com.client
    import winreg
    def forbidden(*args, **kwargs):
        raise AssertionError("discovery must not create CAD or registry keys")
    monkeypatch.setattr(win32com.client, "DispatchEx", forbidden)
    monkeypatch.setattr(winreg, "CreateKey", forbidden)
    monkeypatch.setattr(winreg, "SetValueEx", forbidden)
    result = discovery.discover_candidates("autocad")
    assert len(result) == 1
    assert result[0].executable == registered[0].resolve()
    assert result[0].reported_version == "25.0"


@pytest.mark.parametrize("product", ["AutoCAD LT", "AutoCAD Mechanical", "AutoCAD Civil 3D", "Unknown", ""])
def test_lt_or_unknown_identity_excluded(registered, monkeypatch, product):
    monkeypatch.setattr(discovery, "_file_identity", lambda path: (product, "25.0"))
    with pytest.raises(AppError) as error:
        discovery.discover_candidates("autocad")
    assert error.value.code == "E223"


def test_unquoted_installed_path_with_spaces_is_recognized(registered, monkeypatch):
    exe, raw = registered
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: (
        discovery.Registration(raw.prog_id, raw.clsid, f"{exe} /Automation", None),))
    assert discovery.discover_candidates("autocad")[0].executable == exe.resolve()


def test_ambiguous_unquoted_executable_rejected(registered, monkeypatch):
    exe, raw = registered
    (exe.parent.parent / "CAD.exe").write_bytes(b"ambiguous prefix")
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: (
        discovery.Registration(raw.prog_id, raw.clsid, f"{exe} /Automation", None),))
    with pytest.raises(AppError) as error:
        discovery.discover_candidates("autocad")
    assert error.value.code == "E202"


def test_server_executable_resolves_unquoted_ambiguity(registered, monkeypatch):
    exe, raw = registered
    (exe.parent.parent / "CAD.exe").write_bytes(b"prefix ignored by ServerExecutable")
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: (
        discovery.Registration(raw.prog_id, raw.clsid, f"{exe} /Automation", str(exe)),))
    assert discovery.discover_candidates("autocad")[0].executable == exe.resolve()


def test_conflicting_registration_e202(registered, monkeypatch):
    exe, raw = registered
    other = discovery.Registration(raw.prog_id, "{00000000-0000-0000-0000-000000000024}", raw.command, None)
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: (raw, other))
    with pytest.raises(AppError) as error:
        discovery.discover_candidates("autocad")
    assert error.value.code == "E202"


def test_registry_empty_yields_no_candidates(monkeypatch):
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: ())
    assert discovery.discover_candidates("autocad") == ()


def test_missing_executable_rejected(registered):
    registered[0].unlink()
    with pytest.raises(AppError) as error:
        discovery.discover_candidates("autocad")
    assert error.value.code == "E202"


@pytest.mark.parametrize("command", ["cmd.exe /c acad.exe", "relative/acad.exe", '"C:/CAD/acad.exe', ""])
def test_invalid_server_command_rejected(command):
    with pytest.raises(AppError) as error:
        discovery._server_executable(command, None)
    assert error.value.code == "E202"


def test_metadata_reader_bootstraps_pywin32_without_prior_com_import():
    result = subprocess.run(
        [sys.executable, "-c", "import sys,json; from pathlib import Path; "
         "from dwg_to_pdf.cad.discovery import _file_identity; "
         "print(json.dumps(_file_identity(Path(sys.executable))))"],
        capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert json.loads(result.stdout)[0]


@pytest.mark.parametrize("arguments", ['/product ACADM /Automation', '/product "C3D" /Automation', '/ld "C:/vertical.arx"', '/product ACAD /product ACADM'])
@pytest.mark.parametrize("explicit_server", [False, True])
def test_excluded_or_unverified_launch_mode_rejected(registered, monkeypatch, arguments, explicit_server):
    exe, raw = registered
    record = discovery.Registration(raw.prog_id, raw.clsid, f'"{exe}" {arguments}', str(exe) if explicit_server else None)
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: (record,))
    with pytest.raises(AppError) as error:
        discovery.discover_candidates("autocad")
    assert error.value.code == "E223"


@pytest.mark.parametrize("explicit_server", [False, True])
def test_same_executable_different_launch_arguments_are_conflicting(registered, monkeypatch, explicit_server):
    exe, raw = registered
    records = tuple(discovery.Registration(raw.prog_id, raw.clsid, f'"{exe}" /product {product} /Automation', str(exe) if explicit_server else None) for product in ("ACAD", "ACADM"))
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: records)
    with pytest.raises(AppError) as error:
        discovery.discover_candidates("autocad")
    assert error.value.code == "E202"


def test_normalized_launch_arguments_retained(registered, monkeypatch):
    exe, raw = registered
    records = tuple(discovery.Registration(raw.prog_id, raw.clsid, f'"{exe}" {arguments}', None) for arguments in ('/product "ACAD" /Automation', '/product acad   /automation'))
    monkeypatch.setattr(discovery, "_read_registrations", lambda provider: records)
    result = discovery.discover_candidates("autocad")
    assert len(result) == 1
    assert result[0].launch_arguments == ("/product", "acad", "/automation")
