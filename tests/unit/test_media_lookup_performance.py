import math

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.media_resolver import require_plot_environment


class Layout:
    def __init__(self, sizes):
        self.sizes = sizes
        self.reads = []
        self.CanonicalMediaName = ""

    def GetPlotDeviceNames(self):
        return ["DWG To PDF.pc3"]

    def RefreshPlotDeviceInfo(self):
        pass

    def GetPlotStyleTableNames(self):
        return ["monochrome.ctb"]

    def GetCanonicalMediaNames(self):
        return list(self.sizes)

    def GetPaperSize(self):
        self.reads.append(self.CanonicalMediaName)
        return self.sizes[self.CanonicalMediaName]


def test_unique_preferred_a4_does_not_probe_unrelated_media():
    layout = Layout({"LETTER": (279, 216), "User77": (297, 210), "ISO_A4": (210, 297)})
    assert require_plot_environment(layout, ("User77",)) == "User77"
    assert layout.reads == ["User77"]


def test_all_installed_preferences_are_checked_before_accepting_one():
    layout = Layout({"LETTER": (279, 216), "User77": (297, 210), "OTHER": (210, 297)})
    with pytest.raises(AppError, match="multiple preferred") as raised:
        require_plot_environment(layout, ("User77", "OTHER"))
    assert raised.value.code == "E211"
    assert layout.reads == ["User77", "OTHER"]


@pytest.mark.parametrize("preferences", [("MISSING",), ("LETTER",), ()])
def test_missing_or_wrong_size_preference_uses_dimension_fallback(preferences):
    layout = Layout({"LETTER": (279, 216), "ISO_A4": (210, 297)})
    assert require_plot_environment(layout, preferences) == "ISO_A4"
    assert sorted(layout.reads) == ["ISO_A4", "LETTER"]


def test_fallback_does_not_choose_between_multiple_unpreferred_a4():
    layout = Layout({"FIRST": (297, 210), "SECOND": (210, 297)})
    with pytest.raises(AppError, match="expected one A4"):
        require_plot_environment(layout, ("MISSING",))


def test_invalid_preferred_dimensions_fail_closed():
    layout = Layout({"PREFERRED": (math.nan, 210), "OTHER": (297, 210)})
    with pytest.raises(AppError, match="non-finite"):
        require_plot_environment(layout, ("PREFERRED",))
