"""Exercise real selection/lifetime logic with the Windows ABI boundary faked."""
import ctypes
from types import SimpleNamespace
import pytest


def adapter():
    from dwg_to_pdf import windows_picker
    return windows_picker


class Native:
    def __init__(self, module, monkeypatch, *, failure=None, init=0, defaults=0x1008):
        self.failure = failure
        self.init = init
        self.defaults = defaults
        self.options = None
        self.released = []
        self.freed = []
        self.uninitialized = 0
        self.buffers = []
        self.paths = ("D:/도면 입력/a.dwg", "D:/도면 입력/b.dwg")
        self.filter = None
        monkeypatch.setattr(module, "_load_ole32", lambda: SimpleNamespace(
            CoInitializeEx=lambda *a: init,
            CoUninitialize=self.uninitialize,
            CoCreateInstance=self.create,
            CoTaskMemFree=lambda p: self.freed.append(p.value),
        ))
        monkeypatch.setattr(module._ComPtr, "invoke", lambda ptr, *a, **kw: self.invoke(ptr, *a, **kw))

    def uninitialize(self):
        self.uninitialized += 1

    @staticmethod
    def out(arg, value):
        arg._obj.value = value

    def create(self, clsid, outer, context, iid, out):
        if self.failure == "create":
            return -2147467259
        self.out(out, 1)
        return 0

    def invoke(self, ptr, index, argtypes=(), *args, restype=None):
        identity = ptr.value
        if index == 2:
            self.released.append(identity)
            return 0
        if (identity, index) == self.failure:
            return -2147467259
        if identity == 1:
            if index == 10: self.out(args[0], self.defaults)
            elif index == 9: self.options = args[0]
            elif index == 4: self.filter = (args[1][0].name, args[1][0].spec)
            elif index == 3: return -2147023673 if self.failure == "cancel" else 0
            elif index == 20: self.out(args[0], 3)
            elif index == 27: self.out(args[0], 2)
        elif identity == 2:
            if index == 7: self.out(args[0], len(self.paths))
            elif index == 8: self.out(args[1], 3 + args[0])
        elif identity in (3, 4) and index == 5:
            assert args[0] == 0x80058000
            text = "D:/PDF 출력" if self.options & 0x20 else self.paths[identity - 3]
            buffer = ctypes.create_unicode_buffer(text)
            self.buffers.append(buffer)
            self.out(args[1], ctypes.addressof(buffer))
        return 0


def test_multi_files_preserve_unicode_and_release_all_resources(monkeypatch):
    m = adapter()
    native = Native(m, monkeypatch)
    assert m.pick_dwg_files("DWG 선택") == ("D:/도면 입력/a.dwg", "D:/도면 입력/b.dwg")
    assert native.options == 0x1A48
    assert native.filter == ("DWG 도면 (*.dwg)", "*.dwg")
    assert native.released == [3, 4, 2, 1]
    assert len(native.freed) == 2
    assert native.uninitialized == 1


def test_folder_clears_conflicting_options_but_preserves_other_defaults(monkeypatch):
    m = adapter()
    native = Native(m, monkeypatch, defaults=0x1208, init=1)
    assert m.pick_folder("폴더 선택") == "D:/PDF 출력"
    assert native.options == 0x868
    assert native.filter is None
    assert native.released == [3, 1]
    assert len(native.freed) == 1
    assert native.uninitialized == 1


@pytest.mark.parametrize("folder,expected", [(False, ()), (True, "")])
def test_cancel_returns_empty_and_balances_com(monkeypatch, folder, expected):
    m = adapter()
    native = Native(m, monkeypatch, failure="cancel")
    assert (m.pick_folder if folder else m.pick_dwg_files)("취소") == expected
    assert native.released == [1]
    assert native.uninitialized == 1


@pytest.mark.parametrize("failure,releases", [
    ("create", []), ((1, 10), [1]), ((1, 9), [1]), ((1, 17), [1]),
    ((1, 3), [1]), ((1, 27), [1]), ((2, 7), [2, 1]),
    ((2, 8), [2, 1]), ((3, 5), [3, 2, 1]),
])
def test_non_cancel_errors_raise_and_release_partial_resources(monkeypatch, failure, releases):
    m = adapter()
    native = Native(m, monkeypatch, failure=failure)
    with pytest.raises(OSError): m.pick_dwg_files("에러")
    assert native.released == releases
    assert native.uninitialized == 1


def test_folder_result_error_is_not_cancel(monkeypatch):
    m = adapter()
    native = Native(m, monkeypatch, failure=(1, 20))
    with pytest.raises(OSError): m.pick_folder("에러")
    assert native.released == [1]
    assert native.uninitialized == 1


def test_failed_com_initialization_is_not_uninitialized(monkeypatch):
    m = adapter()
    native = Native(m, monkeypatch, init=-2147417850)
    with pytest.raises(OSError): m.pick_folder("에러")
    assert native.released == []
    assert native.uninitialized == 0
