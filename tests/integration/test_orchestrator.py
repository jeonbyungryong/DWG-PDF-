from __future__ import annotations

from pathlib import Path

import pytest

from dwg_to_pdf.domain import ConvertedFrame, ConversionOutcome, JobResult, Point, Rect, ScaleRatio
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.com_session import GstarSession
from dwg_to_pdf.orchestrator import run_jobs
from dwg_to_pdf.temp_workspace import SourceWorkspace


class FakeSession:
    def __init__(self, pid: int, events: list[str]) -> None:
        self.owned_pid = pid
        self.events = events
        self.is_usable = True

    def __enter__(self):
        self.events.append(f"enter:{self.owned_pid}")
        return self

    def __exit__(self, *_args):
        self.events.append(f"exit:{self.owned_pid}")


class FakeFactory:
    def __init__(self, *, fail_enter_at: int | None = None) -> None:
        self.events: list[str] = []
        self.created_owned_pids: list[int] = []
        self.calls = 0
        self.fail_enter_at = fail_enter_at

    def __call__(self):
        self.calls += 1
        if self.fail_enter_at == self.calls:
            raise AppError("E201", "factory unavailable")
        pid = 2000 + self.calls
        self.created_owned_pids.append(pid)
        return FakeSession(pid, self.events)


class FakeService:
    def __init__(
        self,
        *,
        failures: dict[str, BaseException] | None = None,
        broken_names: set[str] | None = None,
    ) -> None:
        self.failures = failures or {}
        self.broken_names = broken_names or set()
        self.calls: list[tuple[str, int]] = []

    def convert_in_session(self, session, source: Path, _output_dir: Path, _policy: str):
        self.calls.append((source.name, session.owned_pid))
        if source.name in self.broken_names:
            session.is_usable = False
        problem = self.failures.get(source.name)
        if problem is not None:
            raise problem
        output = source.with_suffix(".pdf")
        return ConversionOutcome(
            source,
            (ConvertedFrame(output, ScaleRatio(1, 1), 0, Rect(Point(0, 0), Point(1, 1))),),
        )


def _paths(tmp_path: Path, *names: str) -> tuple[Path, ...]:
    return tuple(tmp_path / name for name in names)


def test_bad_middle_file_does_not_stop_later_file_and_preserves_order(tmp_path: Path) -> None:
    factory = FakeFactory()
    service = FakeService(failures={"bad.dwg": AppError("E303", "non-uniform block scale")})

    results = run_jobs(service, _paths(tmp_path, "a.dwg", "bad.dwg", "c.dwg"), tmp_path, "skip", factory)

    assert [item.status for item in results] == ["success", "failed", "success"]
    assert [item.source.name for item in results] == ["a.dwg", "bad.dwg", "c.dwg"]
    assert results[1].code == "E303"
    assert results[1].reason == "비균일 블록 축척이 검출되었습니다."
    assert factory.created_owned_pids == [2001]
    assert [pid for _, pid in service.calls] == [2001, 2001, 2001]


def test_broken_session_exits_before_one_replacement_and_continues(tmp_path: Path) -> None:
    factory = FakeFactory()
    service = FakeService(
        failures={"bad.dwg": AppError("E203", "document close failed")},
        broken_names={"bad.dwg"},
    )

    results = run_jobs(service, _paths(tmp_path, "bad.dwg", "good.dwg"), tmp_path, "skip", factory)

    assert [item.status for item in results] == ["failed", "success"]
    assert factory.created_owned_pids == [2001, 2002]
    assert factory.events == ["enter:2001", "exit:2001", "enter:2002", "exit:2002"]
    assert service.calls == [("bad.dwg", 2001), ("good.dwg", 2002)]


def test_primary_file_failure_is_preserved_when_replacement_fails(tmp_path: Path) -> None:
    factory = FakeFactory(fail_enter_at=2)
    service = FakeService(
        failures={"bad.dwg": AppError("E400", "source identity changed")},
        broken_names={"bad.dwg"},
    )

    results = run_jobs(service, _paths(tmp_path, "bad.dwg", "later.dwg"), tmp_path, "skip", factory)

    assert results[0].code == "E400"
    assert results[0].reason == "원본 도면 보호 검증에 실패했습니다."
    assert "factory unavailable" in (results[0].log_detail or "")
    assert results[1].code == "E311"
    assert service.calls == [("bad.dwg", 2001)]


class _RawWorkingDocument:
    ReadOnly = False

    def __init__(self, path):
        self.FullName = path

    def Close(self, _save: bool) -> None:
        raise RuntimeError("close failed")


class _WorkingSession(GstarSession):
    def __init__(self, pid: int, events: list[str]) -> None:
        super().__init__("unused")
        self.owned_pid = pid
        self.events = events
        self.app = type("App", (), {"Documents": type("Documents", (), {"Open": lambda _, path, readonly: _RawWorkingDocument(path)})()})()
        self._owns_app = True

    def __enter__(self):
        self.events.append(f"enter:{self.owned_pid}")
        return self

    def __exit__(self, *_args):
        self.events.append(f"exit:{self.owned_pid}")


class _WorkingService:
    def __init__(self, body_error: BaseException | None = None) -> None:
        self.body_error = body_error or AppError("E303", "non-uniform block scale")

    def convert_in_session(self, session, source: Path, _output_dir: Path, _policy: str):
        with SourceWorkspace(source) as workspace:
            with session.working_document(workspace):
                raise self.body_error


class _CloseOnlyWorkingService:
    def convert_in_session(self, session, source: Path, _output_dir: Path, _policy: str):
        with SourceWorkspace(source) as workspace:
            with session.working_document(workspace):
                pass


def test_working_document_close_chain_preserves_body_reason_and_logs_close(tmp_path: Path) -> None:
    source = tmp_path / "body-and-close.dwg"
    source.write_bytes(b"dwg")
    events: list[str] = []
    serial = iter((2001, 2002))
    factory = lambda: _WorkingSession(next(serial), events)

    result = run_jobs(_WorkingService(), (source,), tmp_path, "skip", factory)[0]

    assert result.status == "failed"
    assert result.code == "E303"
    assert result.reason == "비균일 블록 축척이 검출되었습니다."
    assert "E203: AppError: CAD could not close the current document" in (result.log_detail or "")
    assert "E303: AppError: non-uniform block scale" in (result.log_detail or "")
    assert events == ["enter:2001", "exit:2001", "enter:2002", "exit:2002"]


def test_working_document_close_chain_with_runtime_body_normalizes_to_e900_and_logs_both(tmp_path: Path) -> None:
    source = tmp_path / "runtime-and-close.dwg"
    source.write_bytes(b"dwg")
    events: list[str] = []
    serial = iter((2001, 2002))

    result = run_jobs(
        _WorkingService(RuntimeError("detector crashed")),
        (source,),
        tmp_path,
        "skip",
        lambda: _WorkingSession(next(serial), events),
    )[0]

    assert result.status == "failed"
    assert result.code == "E900"
    assert result.reason == "예상하지 못한 변환 오류가 발생했습니다."
    assert "E203: AppError: CAD could not close the current document" in (result.log_detail or "")
    assert "RuntimeError: detector crashed" in (result.log_detail or "")


def test_working_document_close_only_failure_remains_e203_not_e900(tmp_path: Path) -> None:
    source = tmp_path / "close-only.dwg"
    source.write_bytes(b"dwg")
    events: list[str] = []
    serial = iter((2001, 2002))

    result = run_jobs(
        _CloseOnlyWorkingService(),
        (source,),
        tmp_path,
        "skip",
        lambda: _WorkingSession(next(serial), events),
    )[0]

    assert result.status == "failed"
    assert result.code == "E203"
    assert result.reason == "GstarCAD 문서 종료에 실패했습니다."
    assert "E203: AppError: CAD could not close the current document" in (result.log_detail or "")
    assert "RuntimeError: close failed" in (result.log_detail or "")


def test_initial_factory_failure_returns_e311_for_every_input_without_callback(tmp_path: Path) -> None:
    factory = FakeFactory(fail_enter_at=1)
    service = FakeService()

    results = run_jobs(service, _paths(tmp_path, "a.dwg", "b.dwg"), tmp_path, "skip", factory)

    assert [item.code for item in results] == ["E311", "E311"]
    assert service.calls == []


def test_unexpected_exception_normalizes_to_e900_and_control_exception_escapes(tmp_path: Path) -> None:
    factory = FakeFactory()
    results = run_jobs(
        FakeService(failures={"bad.dwg": RuntimeError("boom")}),
        _paths(tmp_path, "bad.dwg", "good.dwg"),
        tmp_path,
        "skip",
        factory,
    )
    assert [item.code for item in results] == ["E900", None]
    assert results[0].reason == "예상하지 못한 변환 오류가 발생했습니다."

    with pytest.raises(KeyboardInterrupt):
        run_jobs(
            FakeService(failures={"stop.dwg": KeyboardInterrupt()}),
            _paths(tmp_path, "stop.dwg"),
            tmp_path,
            "skip",
            FakeFactory(),
        )


def test_success_outputs_and_only_explicit_conflict_skip_is_skipped(tmp_path: Path) -> None:
    results = run_jobs(
        FakeService(
            failures={
                "skip.dwg": AppError("E500", "existing PDF output was not replaced"),
                "write.dwg": AppError("E500", "could not publish PDF"),
            }
        ),
        _paths(tmp_path, "ok.dwg", "skip.dwg", "write.dwg"),
        tmp_path,
        "skip",
        FakeFactory(),
    )
    assert results[0].outputs == (tmp_path / "ok.pdf",)
    assert [item.status for item in results] == ["success", "skipped", "failed"]


def test_orchestrator_does_not_call_file_stability_or_direct_process_cleanup() -> None:
    import dwg_to_pdf.orchestrator as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "require_stable" not in source
    assert "taskkill" not in source.casefold()
    assert "_gstar_pids" not in source


class _ExitFailsSession(FakeSession):
    def __exit__(self, *_args):
        self.events.append(f"exit:{self.owned_pid}")
        raise RuntimeError("terminal session cleanup failed")


class _ControlExitSession(FakeSession):
    def __init__(self, pid: int, events: list[str], control: BaseException) -> None:
        super().__init__(pid, events)
        self.control = control

    def __exit__(self, *_args):
        self.events.append(f"exit:{self.owned_pid}")
        raise self.control


def test_terminal_session_exit_failure_does_not_replace_results_or_keyboardinterrupt(tmp_path: Path) -> None:
    events: list[str] = []
    factory = lambda: _ExitFailsSession(2001, events)
    results = run_jobs(FakeService(), _paths(tmp_path, "ok.dwg"), tmp_path, "skip", factory)
    assert results[0].status == "success"

    with pytest.raises(KeyboardInterrupt):
        run_jobs(
            FakeService(failures={"stop.dwg": KeyboardInterrupt()}),
            _paths(tmp_path, "stop.dwg"),
            tmp_path,
            "skip",
            lambda: _ExitFailsSession(2002, events),
        )


@pytest.mark.parametrize("control", [KeyboardInterrupt(), SystemExit(), GeneratorExit()])
def test_terminal_session_cleanup_control_exception_propagates(tmp_path: Path, control: BaseException) -> None:
    with pytest.raises(type(control)):
        run_jobs(
            FakeService(),
            _paths(tmp_path, "ok.dwg"),
            tmp_path,
            "skip",
            lambda: _ControlExitSession(2001, [], control),
        )


class _FailingEnterSession(FakeSession):
    def __enter__(self):
        self.events.append(f"enter:{self.owned_pid}")
        raise RuntimeError("replacement enter failed")


class _FailingEnterControlCleanupSession(_FailingEnterSession):
    def __init__(self, pid: int, events: list[str], control: BaseException) -> None:
        super().__init__(pid, events)
        self.control = control

    def __exit__(self, *_args):
        self.events.append(f"exit:{self.owned_pid}")
        raise self.control


def test_failed_replacement_enter_runs_its_exit_cleanup(tmp_path: Path) -> None:
    events: list[str] = []
    first = FakeSession(2001, events)
    second = _FailingEnterSession(2002, events)
    sessions = iter((first, second))
    service = FakeService(
        failures={"bad.dwg": AppError("E400", "source identity changed")},
        broken_names={"bad.dwg"},
    )

    results = run_jobs(service, _paths(tmp_path, "bad.dwg", "later.dwg"), tmp_path, "skip", lambda: next(sessions))

    assert results[0].code == "E400"
    assert results[1].code == "E311"
    assert events == ["enter:2001", "exit:2001", "enter:2002", "exit:2002"]


def test_failed_enter_cleanup_control_exception_propagates(tmp_path: Path) -> None:
    events: list[str] = []
    sessions = iter((FakeSession(2001, events), _FailingEnterControlCleanupSession(2002, events, KeyboardInterrupt())))
    service = FakeService(
        failures={"bad.dwg": AppError("E400", "source identity changed")},
        broken_names={"bad.dwg"},
    )

    with pytest.raises(KeyboardInterrupt):
        run_jobs(service, _paths(tmp_path, "bad.dwg"), tmp_path, "skip", lambda: next(sessions))

    assert events == ["enter:2001", "exit:2001", "enter:2002", "exit:2002"]
