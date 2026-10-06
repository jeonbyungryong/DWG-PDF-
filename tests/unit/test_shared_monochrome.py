from types import SimpleNamespace

import pytest

from dwg_to_pdf.cad.monochrome import prepare_monochrome
from dwg_to_pdf.errors import AppError
from test_monochrome_adapters import Collection


class Colored:
    def __init__(self, method=194, rgb=(1, 2, 3), fail=False):
        self.TrueColor = SimpleNamespace(ColorMethod=method, Red=rgb[0], Green=rgb[1], Blue=rgb[2])
        self._color = 256
        self.writes = []
        self.fail = fail
        self.Lineweight = 25
        self.PlotStyleName = "normal"
        self.TextString = "unchanged"

    @property
    def Color(self):
        return self._color

    @Color.setter
    def Color(self, value):
        if self.fail:
            raise RuntimeError("COM write rejected")
        self.writes.append(value)
        self._color = value
        self.TrueColor.ColorMethod = 195


def document(objects=(), layers=()):
    return SimpleNamespace(Layers=Collection(list(layers)), Blocks=Collection([Collection(list(objects))]))


def test_idempotent_white_and_inherited_colors_preserve_other_properties():
    objects = [Colored(), Colored(rgb=(255, 255, 255)), Colored(192), Colored(193), Colored(195)]
    raw = document(objects)
    prepare_monochrome(raw)
    prepare_monochrome(raw)
    assert [obj.writes for obj in objects] == [[7], [], [], [], []]
    assert all((obj.Lineweight, obj.PlotStyleName, obj.TextString) == (25, "normal", "unchanged") for obj in objects)


@pytest.mark.parametrize("method,rgb", [(True, (1, 2, 3)), (999, (1, 2, 3)), (194, (-1, 2, 3)), (194, (1.0, 2, 3)), (194, (256, 2, 3))])
def test_bad_color_info_fails_before_any_write(method, rgb):
    first = Colored()
    with pytest.raises(AppError) as error:
        prepare_monochrome(document([first, Colored(method, rgb)]))
    assert error.value.code == "E410"
    assert first.writes == []


@pytest.mark.parametrize("count", [-1, True, 1.0, 5001])
def test_bad_collection_count_fails_before_any_write(count):
    first = Colored()
    raw = document(layers=[first])
    raw.Blocks.items[0].Count = count
    with pytest.raises(AppError):
        prepare_monochrome(raw)
    assert first.writes == []


def test_default_block_limit_boundary_and_overflow():
    first = Colored()
    raw = document(layers=[first])
    raw.Blocks = Collection([Collection([]) for _ in range(64)])
    prepare_monochrome(raw)
    assert first.writes == [7]
    raw = document(layers=[Colored()])
    raw.Blocks = Collection([Collection([]) for _ in range(65)])
    with pytest.raises(AppError):
        prepare_monochrome(raw)
    assert raw.Layers.items[0].writes == []


def test_aggregate_boundary_includes_layers_entities_and_attributes():
    attribute = Colored()
    insert = Colored(192)
    insert.HasAttributes = True
    insert.GetAttributes = lambda: (attribute,)
    insert.GetConstantAttributes = lambda: ()
    raw = document([insert], [Colored(192) for _ in range(4998)])
    prepare_monochrome(raw)
    assert attribute.writes == [7]
    attribute = Colored()
    insert.GetAttributes = lambda: (attribute,)
    raw.Layers = Collection([Colored(192) for _ in range(4999)])
    with pytest.raises(AppError):
        prepare_monochrome(raw)
    assert attribute.writes == []


def test_partial_write_failure_reports_e410_without_claiming_rollback():
    first, rejected, last = Colored(), Colored(fail=True), Colored()
    with pytest.raises(AppError) as error:
        prepare_monochrome(document([first, rejected, last]))
    assert error.value.code == "E410"
    assert first.writes == [7]
    assert rejected.writes == last.writes == []
    assert isinstance(error.value.__cause__, RuntimeError)


def test_unknown_xref_status_fails_before_mutation():
    first = Colored()
    raw = document(layers=[first])
    del raw.Blocks.items[0].IsXRef
    with pytest.raises(AppError) as error:
        prepare_monochrome(raw)
    assert error.value.code == "E410"
    assert first.writes == []


def test_xref_read_failure_fails_before_mutation():
    class UnreadableBlock(Collection):
        @property
        def IsXRef(self):
            raise AttributeError("COM XRef status unreadable")

        @IsXRef.setter
        def IsXRef(self, value):
            pass

    first = Colored()
    raw = document(layers=[first])
    raw.Blocks = Collection([UnreadableBlock([])])
    with pytest.raises(AppError) as error:
        prepare_monochrome(raw)
    assert error.value.code == "E410"
    assert first.writes == []
