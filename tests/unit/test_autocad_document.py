from types import SimpleNamespace
import json
import pytest

from dwg_to_pdf.autocad.document import AutoCADDocument
from dwg_to_pdf.autocad import native_extract
from dwg_to_pdf.cad.bulk_snapshot import parse_snapshot, NativeExtractionUnavailable
from dwg_to_pdf.errors import AppError


def ready_app():
    return SimpleNamespace(GetAcadState=lambda: SimpleNamespace(IsQuiescent=True))


def raw_text(value="Scale"):
    raw = parse_snapshot(json.dumps({"version": 1, "token": "n", "document": "C:/work.dwg", "complete": True,
        "entities": [{"ObjectName": "AcDbText", "Handle": "1", "TextString": value, "InsertionPoint": [1, 2, 0]}], "blocks": {}}), "n", "C:/work.dwg")
    raw.Application = ready_app()
    return raw


def test_com_and_native_snapshot_decisions_equal(monkeypatch):
    raw = raw_text()
    calls = []
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda *args: calls.append(1) or raw)
    off = AutoCADDocument(raw)
    on = AutoCADDocument(raw, _bulk_enabled=True)
    assert off.for_scale_detection().filtered_snapshots(("TEXT",)) == on.for_scale_detection().filtered_snapshots(("TEXT",))
    assert calls == [1]


def test_cache_does_not_cross_documents(monkeypatch):
    first, second = raw_text("1:1"), raw_text("2:1")
    calls = []
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda raw, *args: calls.append(raw) or raw)
    a, b = AutoCADDocument(first, _bulk_enabled=True), AutoCADDocument(second, _bulk_enabled=True)
    for document, expected in ((a, "1:1"), (a, "1:1"), (b, "2:1")):
        assert document.for_scale_detection().filtered_snapshots(("TEXT",))[0]["text"] == expected
    assert calls == [first, second]


def test_identified_complete_unavailable_falls_back_once(monkeypatch):
    calls = []
    def unavailable(*args):
        calls.append(1)
        raise NativeExtractionUnavailable("unsupported")
    monkeypatch.setattr(native_extract, "extract_snapshot", unavailable)
    document = AutoCADDocument(raw_text(), _bulk_enabled=True)
    for _ in range(2):
        assert document.for_scale_detection().filtered_snapshots(("TEXT",))[0]["text"] == "Scale"
    assert calls == [1]


def test_identity_failure_has_no_fallback(monkeypatch):
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda *args: (_ for _ in ()).throw(AppError("E303", "identity mismatch")))
    with pytest.raises(AppError, match="identity"):
        AutoCADDocument(raw_text(), _bulk_enabled=True).for_scale_detection()


def test_busy_entity_read_is_retried_without_repeating_selection_mutations(monkeypatch):
    import pywintypes
    from types import SimpleNamespace
    calls = []
    class Entity:
        ObjectName = "AcDbText"
        Handle = "1"
        InsertionPoint = (0., 0., 0.)
        reads = 0
        @property
        def TextString(self):
            self.reads += 1
            if self.reads == 1:
                raise pywintypes.com_error(-2147418111, "busy reading text", None, None)
            return "1:1"
    entity = Entity()
    selection = SimpleNamespace(Count=1, Item=lambda index: entity,
        Select=lambda *args: calls.append("select"), Delete=lambda: calls.append("delete"))
    class Selections:
        def Item(self, name): raise KeyError(name)
        def Add(self, name):
            calls.append("add")
            return selection
    document = AutoCADDocument(SimpleNamespace(SelectionSets=Selections(), Application=ready_app()))
    result = document.filtered_snapshots(("TEXT",))
    assert result[0]["text"] == "1:1"
    assert entity.reads == 2
    assert calls == ["add", "select", "delete"]


@pytest.mark.parametrize("hresult,expired", [(-1, False), (-2147418111, True)])
def test_filtered_read_failure_or_timeout_does_not_repeat_mutations(monkeypatch, hresult, expired):
    import pywintypes
    from types import SimpleNamespace
    from dwg_to_pdf.autocad import document as adapter
    from dwg_to_pdf.cad.com_document import ComDocument
    calls = []
    def fail(self, reader):
        calls.append("read")
        raise pywintypes.com_error(hresult, "failure", None, None)
    monkeypatch.setattr(ComDocument, "_read_com", fail)
    if expired:
        ticks = [0.]
        def clock():
            ticks[0] += 31.
            return ticks[0]
        monkeypatch.setattr(adapter.time, "monotonic", clock)
    monkeypatch.setattr(adapter.time, "sleep", lambda seconds: pytest.fail("must not retry"))
    selection = SimpleNamespace(Count=1, Item=lambda index: object(),
        Select=lambda *args: calls.append("select"), Delete=lambda: calls.append("delete"))
    class Selections:
        def Item(self, name): raise KeyError(name)
        def Add(self, name):
            calls.append("add")
            return selection
    with pytest.raises(AppError):
        AutoCADDocument(SimpleNamespace(SelectionSets=Selections(), Application=ready_app())).filtered_snapshots(("TEXT",))
    assert calls == ["add", "select", "read", "delete"]


def test_selection_mutations_wait_for_ready_and_run_once():
    import pywintypes
    from types import SimpleNamespace
    pending = [2]
    calls = []
    def state():
        pending[0] = max(0, pending[0] - 1)
        return SimpleNamespace(IsQuiescent=pending[0] == 0)
    def mutate(name):
        if pending[0]: raise pywintypes.com_error(-2147418111, "busy mutation", None, None)
        calls.append(name)
        if name != "delete": pending[0] = 2
    entity = SimpleNamespace(ObjectName="AcDbText", TextString="1:1", Handle="1", InsertionPoint=(0.,0.,0.))
    selection = SimpleNamespace(Count=1, Item=lambda index: entity,
        Select=lambda *args: mutate("select"), Delete=lambda: mutate("delete"))
    class Selections:
        def Item(self, name): raise KeyError(name)
        def Add(self, name):
            mutate("add")
            return selection
    raw = SimpleNamespace(SelectionSets=Selections(),Application=SimpleNamespace(GetAcadState=state))
    assert AutoCADDocument(raw).filtered_snapshots(("TEXT",))[0]["text"] == "1:1"
    assert calls == ["add", "select", "delete"]


def test_native_pure_snapshot_view_never_queries_cad_readiness(monkeypatch):
    from dwg_to_pdf.autocad import readiness
    pure = raw_text()
    del pure.Application
    monkeypatch.setattr(native_extract, "extract_snapshot", lambda *args: pure)
    monkeypatch.setattr(readiness, "wait_for_document_ready", lambda *args, **kwargs: pytest.fail("pure snapshot must not query CAD"))
    document = AutoCADDocument(raw_text(), _bulk_enabled=True)
    assert document.for_scale_detection().filtered_snapshots(("TEXT",))[0]["text"] == "Scale"


@pytest.mark.parametrize("mode", ["text", "geometry", "noncontributing"])
def test_busy_nested_block_read_does_not_repeat_traversal_budget(mode):
    import pywintypes
    from dwg_to_pdf.cad.com_document import TraversalBudget
    entity = SimpleNamespace(ObjectName="AcDbLine", Handle="1", StartPoint=(0.,0.,0.), EndPoint=(10.,0.,0.))
    block = SimpleNamespace(Count=1, Item=lambda index: entity)
    reads = []
    class Blocks:
        def Item(self, name):
            reads.append(name)
            if len(reads) == 1:
                raise pywintypes.com_error(-2147418111, "busy block read", None, None)
            return block
    document = AutoCADDocument(SimpleNamespace(Blocks=Blocks()))
    reference = {"block_name":"ROOT", "handle":"A", "point":(0.,0.),
        "rotation":0., "x_scale":1., "y_scale":1.}
    budget = TraversalBudget(1, 1, 1)
    budget.visit_root()
    if mode == "text":
        assert len(document.nested_text_snapshots(reference, budget=budget)) == 1
    elif mode == "geometry":
        assert len(document.nested_geometry_snapshots(reference, budget=budget)) == 1
    else:
        assert document.is_noncontributing_text_insert(reference, budget=budget)
    assert reads == ["ROOT", "ROOT"]
    assert (budget.roots, budget.blocks, budget.entities) == (1, 1, 1)


@pytest.mark.parametrize("mode", ["text", "geometry", "noncontributing"])
def test_nested_entity_metadata_retry_does_not_repeat_traversal(mode,monkeypatch):
    import pywintypes
    from win32com.client.dynamic import CDispatch
    from win32com.client.build import DispatchItem
    from dwg_to_pdf.cad.com_document import TraversalBudget
    from dwg_to_pdf.autocad import document as adapter
    metadata=[];items=[];blocks=[]
    class Ole:
        def GetIDsOfNames(self,locale,name):
            metadata.append(name)
            if len(metadata)==1:
                raise pywintypes.com_error(-2147418111,"busy metadata",None,None)
            return 1
        def Invoke(self,*args):return "AcDbLine"
    dispatch=CDispatch(Ole(),DispatchItem(),"Item")
    class Entity:
        Handle="1";StartPoint=(0.,0.,0.);EndPoint=(10.,0.,0.)
        @property
        def ObjectName(self):return dispatch.ObjectName
    entity=Entity()
    def item(index):items.append(index);return entity
    block=SimpleNamespace(Count=1,Item=item)
    def reached(name):blocks.append(name);return block
    document=AutoCADDocument(SimpleNamespace(Blocks=SimpleNamespace(Item=reached)))
    monkeypatch.setattr(adapter.time,"sleep",lambda seconds:None)
    reference={"block_name":"ROOT","handle":"A","point":(0.,0.),"rotation":0.,"x_scale":1.,"y_scale":1.}
    budget=TraversalBudget(1,1,1);budget.visit_root()
    if mode=="text":assert len(document.nested_text_snapshots(reference,budget=budget))==1
    elif mode=="geometry":assert len(document.nested_geometry_snapshots(reference,budget=budget))==1
    else:assert document.is_noncontributing_text_insert(reference,budget=budget)
    assert metadata==["ObjectName","ObjectName"]
    assert blocks==["ROOT"] and items==[0]
    assert (budget.roots,budget.blocks,budget.entities)==(1,1,1)


def test_direct_metadata_error_retries_only_supplied_reader(monkeypatch):
    from dwg_to_pdf.autocad import document as adapter
    calls=[]
    def reader():
        calls.append(1)
        if len(calls)==1:raise AttributeError("Item.ObjectName")
        return "AcDbLine"
    monkeypatch.setattr(adapter.time,"sleep",lambda seconds:None)
    assert AutoCADDocument(object())._read_com(reader)=="AcDbLine"
    assert len(calls)==2


@pytest.mark.parametrize("wrapped",[False,True])
def test_persistent_metadata_read_keeps_existing_timeout(monkeypatch,wrapped):
    from dwg_to_pdf.autocad import document as adapter
    ticks=iter([0.,31.]);calls=[];clock_reads=[]
    def clock():
        value=next(ticks);clock_reads.append(value);return value
    def reader():
        calls.append(1)
        try:raise AttributeError("Item.ObjectName")
        except AttributeError as error:
            if wrapped:raise AppError("E303","could not snapshot entity type") from error
            raise
    monkeypatch.setattr(adapter.time,"monotonic",clock)
    monkeypatch.setattr(adapter.time,"sleep",lambda seconds:pytest.fail("must not exceed timeout"))
    with pytest.raises(AppError if wrapped else AttributeError):
        AutoCADDocument(object())._read_com(reader)
    assert calls==[1]
    assert clock_reads==[0.,31.]
