from ..cad.com_document import ComDocument


class AutoCADDocument(ComDocument):
    def configure_plotter(self, path):
        self._plot_config = path.resolve(strict=True)

    def _extract_snapshot(self, types=("TEXT", "MTEXT", "INSERT"), bounds=None):
        from .native_extract import extract_snapshot
        return extract_snapshot(self.raw, types, bounds)

    def plot_pdf(self, output, window, rotation, preferred_media_names):
        from .plotting import plot_pdf
        plot_pdf(self.raw, output, window, rotation, preferred_media_names,
                 plot_config=getattr(self, "_plot_config", None))
