"""Explicit environment gate for live experimental AutoCAD tests."""
from pathlib import Path


def live_autocad_environment(environment):
    names = ("AUTOCAD_TEST_CONFIG", "AUTOCAD_TEST_DWGS")
    if environment.get("AUTOCAD_TEST_ENABLED") != "1" or any(not environment.get(name) for name in names):
        raise ValueError("AutoCAD NOT_RUN: set AUTOCAD_TEST_ENABLED=1, AUTOCAD_TEST_CONFIG and AUTOCAD_TEST_DWGS")
    config = Path(environment["AUTOCAD_TEST_CONFIG"])
    sources = tuple(Path(value.strip()) for value in environment["AUTOCAD_TEST_DWGS"].split(";") if value.strip())
    if not config.is_absolute() or not sources or any(not source.is_absolute() for source in sources):
        raise ValueError("AutoCAD NOT_RUN: config and DWG paths must be absolute")
    return config, sources


def require_process_cleanup(user_pids, acquired_pids, after_pids):
    assert set(user_pids) <= set(after_pids), "a pre-existing user CAD process disappeared"
    assert not set(acquired_pids) & set(after_pids), "an acquired CAD PID is still present after cleanup"
