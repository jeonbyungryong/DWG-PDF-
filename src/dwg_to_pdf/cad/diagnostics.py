"""Allowlisted public diagnostics; never include drawings, paths or traceback."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import sys

_state = ContextVar("cad_diagnostic_state", default=None)


def build_diagnostic_record(provider, prog_id, reported_version, app_version, stage, code):
    return dict(provider=provider, prog_id=prog_id, reported_version=reported_version,
                app_version=app_version, stage=stage, code=code)


@contextmanager
def diagnostic_scope(candidate, app_version):
    token = _state.set(dict(provider=candidate.provider, prog_id=candidate.prog_id,
                           reported_version=None, app_version=app_version))
    try:
        yield
    finally:
        _state.reset(token)


def emit(stage, code=None, *, reported_version=None):
    state = _state.get()
    if state is None:
        return
    if stage == "start":
        state["reported_version"] = None
    if reported_version is not None:
        state["reported_version"] = reported_version
    record = build_diagnostic_record(**state, stage=stage, code=code)
    print("CAD_DIAGNOSTIC " + json.dumps(record, ensure_ascii=True), file=sys.stderr)
