import os
import pytest

from dwg_to_pdf.cad.validation import live_autocad_environment


@pytest.fixture(autouse=True)
def gate_live_autocad(request):
    if request.node.get_closest_marker("autocad") is not None:
        try:
            live_autocad_environment(os.environ)
        except ValueError as error:
            pytest.skip(str(error))
