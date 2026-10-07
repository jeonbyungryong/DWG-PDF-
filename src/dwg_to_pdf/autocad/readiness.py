import time

import pythoncom
import pywintypes

from ..errors import AppError


def wait_for_document_ready(raw, *, error_code: str = "E410") -> None:
    """Poll read-only state before a mutation; never retry the mutation."""
    deadline = time.monotonic() + 30.0
    while True:
        pythoncom.PumpWaitingMessages()
        try:
            if raw.Application.GetAcadState().IsQuiescent:
                return
        except pywintypes.com_error as exc:
            if exc.hresult not in (-2147418111, -2147417846):
                raise
        if time.monotonic() >= deadline:
            raise AppError(error_code, "AutoCAD did not become ready within 30 seconds")
        time.sleep(0.05)


