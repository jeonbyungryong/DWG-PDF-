import time

import pythoncom
import pywintypes

from ..cad.com_session import ComSession
from ..cad.selection import CadCandidate
from ..errors import AppError


class AutoCADSession(ComSession):
    def __init__(self, candidate: CadCandidate) -> None:
        if candidate.provider != "autocad":
            raise AppError("E202", "AutoCAD session requires an AutoCAD candidate")
        def document_factory(raw):
            from .document import AutoCADDocument
            return AutoCADDocument(raw)
        super().__init__(candidate, document_factory)

    def _wait_until_ready(self) -> None:
        self._wait_for_ready(120.0)

    def _after_document_open(self) -> None:
        self._wait_for_ready(30.0, min_documents=1)

    def _before_document_close(self) -> None:
        self._wait_for_ready(30.0)

    def _wait_for_ready(self, timeout_sec: float, *, min_documents: int = 0) -> None:
        # Read-only polling; never retry Open/SendCommand or other mutations.
        deadline = time.monotonic() + timeout_sec
        while True:
            try:
                if self.app.GetAcadState().IsQuiescent and int(self.app.Documents.Count) >= min_documents:
                    return
            except pywintypes.com_error as error:
                if error.hresult not in (-2147418111, -2147417846):
                    raise AppError("E201", "AutoCAD readiness query failed") from error
            except AttributeError:
                # Startup may temporarily expose incomplete dispatch metadata.
                pass
            if time.monotonic() >= deadline:
                raise AppError("E201", f"AutoCAD did not become ready within {timeout_sec:g} seconds")
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)
