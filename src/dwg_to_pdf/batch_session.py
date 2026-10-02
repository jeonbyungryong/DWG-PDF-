from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .errors import AppError


T = TypeVar("T")
_CONTROL_EXCEPTIONS = (KeyboardInterrupt, SystemExit, GeneratorExit)


class BatchSession:
    """Own one reusable APP-created session and replace it only when unusable.

    ConversionService owns each document boundary.  This class deliberately
    does not open or close documents; it only owns the COM-session lifetime.
    """

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._session: Any | None = None
        self._unavailable = False
        self.last_cleanup_error: BaseException | None = None

    def __enter__(self) -> "BatchSession":
        session: Any | None = None
        try:
            session = self._factory()
            session.__enter__()
            self._session = session
        except BaseException as exc:
            self._exit_failed_session(session, exc)
            self._session = None
            self._unavailable = True
            if not isinstance(exc, Exception):
                raise
            raise AppError("E311", "GstarCAD batch session is unavailable") from exc
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        session, self._session = self._session, None
        if session is not None:
            try:
                session.__exit__(exc_type, exc, tb)
            except BaseException as cleanup_error:
                if isinstance(cleanup_error, _CONTROL_EXCEPTIONS):
                    raise
                # Terminal cleanup must not replace already accumulated
                # results or a control exception from the callback.
                self.last_cleanup_error = cleanup_error

    @staticmethod
    def _exit_failed_session(session: Any | None, error: BaseException) -> None:
        if session is None:
            return
        try:
            session.__exit__(type(error), error, error.__traceback__)
        except BaseException as cleanup_error:
            if isinstance(cleanup_error, _CONTROL_EXCEPTIONS):
                raise
            error.add_note(
                f"Replacement session cleanup failure: {type(cleanup_error).__name__}: {cleanup_error}"
            )

    @property
    def is_available(self) -> bool:
        return not self._unavailable and self._session is not None

    def _replace(self) -> None:
        old, self._session = self._session, None
        if old is not None:
            old.__exit__(None, None, None)
        replacement: Any | None = None
        try:
            replacement = self._factory()
            replacement.__enter__()
        except BaseException as exc:
            self._exit_failed_session(replacement, exc)
            self._unavailable = True
            if not isinstance(exc, Exception):
                raise
            raise AppError("E311", "GstarCAD batch session is unavailable") from exc
        self._session = replacement

    def run_one(self, callback: Callable[[Any], T]) -> T:
        """Run one conversion and replace the session only after it breaks.

        A callback error is re-raised untouched so its file-specific code is
        retained.  Replacement failure is recorded for the orchestrator to
        append as technical detail, while later files fail as E311.
        """

        if not self.is_available:
            raise AppError("E311", "GstarCAD batch session is unavailable")
        assert self._session is not None
        self.last_cleanup_error = None
        primary: BaseException | None = None
        try:
            return callback(self._session)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            session = self._session
            if session is not None and not bool(getattr(session, "is_usable", False)):
                try:
                    self._replace()
                except Exception as replacement_error:
                    self.last_cleanup_error = replacement_error
                    if primary is None:
                        raise AppError("E311", "GstarCAD batch session is unavailable") from replacement_error
