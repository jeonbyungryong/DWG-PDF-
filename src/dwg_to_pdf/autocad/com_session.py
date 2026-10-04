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
        # Read-only polling; never retry Open/SendCommand or other mutations.
        deadline = time.monotonic() + 120.0
        while True:
            try:
                if self.app.GetAcadState().IsQuiescent and int(self.app.Documents.Count) >= 0:
                    return
            except pywintypes.com_error as error:
                if error.hresult not in (-2147418111, -2147417846):
                    raise AppError("E201", "AutoCAD readiness query failed") from error
            except AttributeError:
                # Startup may temporarily expose incomplete dispatch metadata.
                pass
            if time.monotonic() >= deadline:
                raise AppError("E201", "AutoCAD did not become ready within 120 seconds")
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)
