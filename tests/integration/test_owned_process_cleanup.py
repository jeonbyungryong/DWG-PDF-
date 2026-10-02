from types import SimpleNamespace

import dwg_to_pdf.gstarcad.com_session as com_session


def _session(owned_pid: int, handle: object | None) -> com_session.GstarSession:
    session = com_session.GstarSession("unused")
    session.owned_pid = owned_pid
    session._owned_process_handle = handle
    session._owns_app = True
    session.app = SimpleNamespace(Quit=lambda: None)
    session._com_initialized = False
    session.mutex = None
    return session


def test_owned_cleanup_terminates_only_exact_captured_process_when_pid_is_reused(monkeypatch) -> None:
    owned_pid = 701
    reused_user_pid = 701
    handle = object()
    calls: list[object] = []
    session = _session(owned_pid, handle)

    monkeypatch.setattr(com_session, "_wait_for_process_exit", lambda captured: False)
    monkeypatch.setattr(
        com_session,
        "_terminate_owned_process_handle",
        lambda captured: calls.append(("terminate", captured)),
    )
    monkeypatch.setattr(
        com_session,
        "_close_process_handle",
        lambda captured: calls.append(("close", captured)),
    )

    session._release()

    assert reused_user_pid == owned_pid  # A numeric PID could now belong to a user process.
    assert calls == [("terminate", handle), ("close", handle)]


def test_owned_cleanup_does_not_terminate_when_quit_exits_exact_process(monkeypatch) -> None:
    handle = object()
    calls: list[object] = []
    session = _session(701, handle)

    monkeypatch.setattr(com_session, "_wait_for_process_exit", lambda captured: True)
    monkeypatch.setattr(
        com_session,
        "_terminate_owned_process_handle",
        lambda captured: calls.append(("terminate", captured)),
    )
    monkeypatch.setattr(
        com_session,
        "_close_process_handle",
        lambda captured: calls.append(("close", captured)),
    )

    session._release()

    assert calls == [("close", handle)]


def test_manually_constructed_session_without_exact_handle_never_force_terminates(monkeypatch) -> None:
    calls: list[object] = []
    session = _session(701, None)

    monkeypatch.setattr(
        com_session,
        "_terminate_owned_process_handle",
        lambda captured: calls.append(("terminate", captured)),
    )

    session._release()

    assert calls == []
