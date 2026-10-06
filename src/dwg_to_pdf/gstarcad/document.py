"""GstarCAD adapter and compatibility exports for the shared snapshot model."""
from ..cad.com_document import ComDocument, TraversalBudget, _snapshot
from .media_resolver import require_plot_environment
from .plot_settings import apply_plot_settings
from .plotter import plot_to_file
from ..pdf_orientation import normalize_portrait_plot


class GstarDocument(ComDocument):
    def _extract_snapshot(self, types=("TEXT", "MTEXT", "INSERT"), bounds=None):
        from .bulk_snapshot import extract_snapshot
        return extract_snapshot(self.raw, types, bounds)

    def plot_pdf(self, output, window, rotation, preferred_media_names):
        from ..cad.monochrome import prepare_monochrome
        prepare_monochrome(self.raw)
        layout = self.raw.ActiveLayout
        media = require_plot_environment(layout, preferred_media_names)
        apply_plot_settings(layout, window, rotation, media)
        plot_to_file(self.raw, output)
        normalize_portrait_plot(output, rotation)
