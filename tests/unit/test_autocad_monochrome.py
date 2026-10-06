from types import SimpleNamespace
import pytest
from dwg_to_pdf.errors import AppError

class Collection:
    def __init__(self,items):self.items=items; self.Count=len(items); self.IsXRef=False
    def Item(self,index):return self.items[index]

def item(method,rgb=(0,255,0)):
    return SimpleNamespace(TrueColor=SimpleNamespace(ColorMethod=method,Red=rgb[0],Green=rgb[1],Blue=rgb[2]),Color=256,Lineweight=25)

def test_only_nonwhite_true_colors_in_layers_and_nested_block_definitions_change():
    from dwg_to_pdf.autocad.monochrome import prepare_monochrome
    layer=item(194); nested=item(194); white=item(194,(255,255,255)); indexed=item(195); inherited=item(192)
    raw=SimpleNamespace(Layers=Collection([layer]),Blocks=Collection([Collection([nested,white,indexed,inherited])]))
    prepare_monochrome(raw)
    assert layer.Color==nested.Color==7
    assert white.Color==indexed.Color==inherited.Color==256
    assert all(obj.Lineweight==25 for obj in (layer,nested,white,indexed,inherited))

def test_traversal_limit_and_read_error_fail_before_mutations():
    from dwg_to_pdf.autocad.monochrome import prepare_monochrome
    obj=item(194); raw=SimpleNamespace(Layers=Collection([obj]),Blocks=Collection([Collection([obj])]))
    with pytest.raises(AppError):prepare_monochrome(raw,max_entities=1)
    assert obj.Color==256
    raw.Blocks=Collection([Collection([SimpleNamespace()])])
    with pytest.raises(AppError):prepare_monochrome(raw)
    assert obj.Color==256


def test_attached_and_constant_attributes_are_bounded_before_writes():
    from dwg_to_pdf.autocad.monochrome import prepare_monochrome
    attached=item(194); constant=item(194); insert=item(192)
    insert.HasAttributes=True
    insert.GetAttributes=lambda:(attached,)
    insert.GetConstantAttributes=lambda:(constant,)
    raw=SimpleNamespace(Layers=Collection([]),Blocks=Collection([Collection([insert])]))
    with pytest.raises(AppError):prepare_monochrome(raw,max_entities=2)
    assert attached.Color==constant.Color==256
    prepare_monochrome(raw)
    assert attached.Color==constant.Color==7
