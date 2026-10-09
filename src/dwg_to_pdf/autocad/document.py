import time

import pythoncom
import pywintypes

from ..errors import AppError
from ..cad.com_document import ComDocument


class AutoCADDocument(ComDocument):
    def _before_selection_mutation(self) -> None:
        # Native views select from a verified pure snapshot model, not CAD.
        if self._bulk_raw is not None and self.raw is self._bulk_raw:
            return
        from .readiness import wait_for_document_ready
        wait_for_document_ready(self.raw, error_code="E303")

    def _read_com(self, reader):
        # Only repeat the supplied read; never Add/Select/Delete or traversal.
        deadline = time.monotonic() + 30.0
        while True:
            try:
                return super()._read_com(reader)
            except (AppError, pywintypes.com_error, AttributeError) as error:
                cause = error
                seen = set()
                busy = False
                while cause is not None and id(cause) not in seen:
                    seen.add(id(cause))
                    if isinstance(cause, AttributeError):
                        # pywin32 can hide a busy metadata lookup in this chain.
                        busy = True
                        break
                    if isinstance(cause, pywintypes.com_error):
                        busy = cause.hresult in (-2147418111, -2147417846)
                        break
                    cause = cause.__cause__
                if not busy or time.monotonic() >= deadline:
                    raise
                pythoncom.PumpWaitingMessages()
                time.sleep(0.05)

    def configure_plotter(self, path):
        self._plot_config = path.resolve(strict=True)

    def _extract_snapshot(self, types=("TEXT", "MTEXT", "INSERT"), bounds=None):
        from .native_extract import extract_snapshot
        return extract_snapshot(self.raw, types, bounds)

    def plot_pdf(self, output, window, rotation, preferred_media_names):
        from .plotting import plot_pdf
        plot_pdf(self.raw, output, window, rotation, preferred_media_names,
                 plot_config=getattr(self, "_plot_config", None))
