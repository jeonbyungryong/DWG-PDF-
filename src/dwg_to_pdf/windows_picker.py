"""Windows Common Item Dialogs, loaded lazily without external dependencies.

COM vtable positions follow Microsoft's ShObjIdl_core.h. All interface and
CoTaskMem ownership is confined to this module; paths never pass through a shell.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
import sys
import uuid

_DWORD = ctypes.c_uint32
_HRESULT = ctypes.c_int32
_PTR = ctypes.c_void_p
_PVOID = ctypes.POINTER(_PTR)
_CANCELLED = 0x800704C7
_PICKFOLDERS = 0x20
_MULTISELECT = 0x200
_FILESYSTEM = 0x40
_PATH_EXISTS = 0x800
_FILE_EXISTS = 0x1000


class _GUID(ctypes.Structure):
    _fields_ = [("data1", _DWORD), ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, value: str):
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


class _Filter(ctypes.Structure):
    _fields_ = [("name", ctypes.c_wchar_p), ("spec", ctypes.c_wchar_p)]


def _check(hr: int, stage: str) -> None:
    if hr & 0x80000000:
        raise OSError(f"Windows 경로 선택 실패 ({stage}, HRESULT=0x{hr & 0xFFFFFFFF:08X})")


def _load_ole32():
    if sys.platform != "win32":
        raise OSError("Windows 경로 선택창은 Windows에서만 사용할 수 있습니다.")
    ole = ctypes.WinDLL("ole32")
    ole.CoInitializeEx.argtypes = [_PTR, _DWORD]
    ole.CoInitializeEx.restype = _HRESULT
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), _PTR, _DWORD,
                                    ctypes.POINTER(_GUID), _PVOID]
    ole.CoCreateInstance.restype = _HRESULT
    ole.CoTaskMemFree.argtypes = [_PTR]
    ole.CoTaskMemFree.restype = None
    return ole


class _ComPtr:
    def __init__(self, value: int):
        self.value = value

    def invoke(self, index: int, argtypes=(), *args, restype=_HRESULT):
        vtable = ctypes.cast(_PTR(self.value), ctypes.POINTER(ctypes.POINTER(_PTR))).contents
        method = ctypes.WINFUNCTYPE(restype, _PTR, *argtypes)(vtable[index])
        return method(self.value, *args)

    def release(self):
        if self.value:
            self.invoke(2, restype=_DWORD)
            self.value = 0


@contextmanager
def _interface(stage: str, getter):
    out = _PTR()
    try:
        _check(getter(ctypes.byref(out)), stage)
        if not out.value:
            raise OSError(f"Windows 경로 선택 실패 ({stage}: empty interface)")
        yield _ComPtr(out.value)
    finally:
        if out.value:
            _ComPtr(out.value).release()


def _path(item: _ComPtr, ole) -> str:
    allocated = _PTR()
    try:
        _check(item.invoke(5, (_DWORD, _PVOID), 0x80058000, ctypes.byref(allocated)), "GetDisplayName")
        if not allocated.value:
            raise OSError("Windows 경로 선택 실패 (empty filesystem path)")
        return ctypes.wstring_at(allocated.value)
    finally:
        if allocated.value:
            ole.CoTaskMemFree(allocated)


def _pick(title: str, *, folder: bool) -> tuple[str, ...]:
    ole = _load_ole32()
    # S_OK and S_FALSE both acquire an initialization reference. Failed init
    # (including RPC_E_CHANGED_MODE) must not call CoUninitialize or be retried.
    _check(ole.CoInitializeEx(None, 2), "CoInitializeEx")
    try:
        clsid = _GUID.parse("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")
        iid = _GUID.parse("D57C7288-D4AD-4768-BE02-9D969532D960")
        with _interface("CoCreateInstance", lambda out: ole.CoCreateInstance(
            ctypes.byref(clsid), None, 1, ctypes.byref(iid), out,
        )) as dialog:
            defaults = _DWORD()
            _check(dialog.invoke(10, (ctypes.POINTER(_DWORD),), ctypes.byref(defaults)), "GetOptions")
            options = defaults.value | _FILESYSTEM | _PATH_EXISTS
            if folder:
                options = (options & ~(_MULTISELECT | _FILE_EXISTS)) | _PICKFOLDERS
            else:
                options = (options & ~_PICKFOLDERS) | _MULTISELECT | _FILE_EXISTS
            _check(dialog.invoke(9, (_DWORD,), options), "SetOptions")
            _check(dialog.invoke(17, (ctypes.c_wchar_p,), title), "SetTitle")
            if not folder:
                filters = (_Filter * 1)(_Filter("DWG 도면 (*.dwg)", "*.dwg"))
                _check(dialog.invoke(4, (_DWORD, ctypes.POINTER(_Filter)), 1, filters), "SetFileTypes")
            hr = dialog.invoke(3, (_PTR,), None)
            if hr & 0xFFFFFFFF == _CANCELLED:
                return ()
            _check(hr, "Show")
            if folder:
                with _interface("GetResult", lambda out: dialog.invoke(20, (_PVOID,), out)) as item:
                    return (_path(item, ole),)
            with _interface("GetResults", lambda out: dialog.invoke(27, (_PVOID,), out)) as items:
                count = _DWORD()
                _check(items.invoke(7, (ctypes.POINTER(_DWORD),), ctypes.byref(count)), "GetCount")
                paths = []
                for index in range(count.value):
                    with _interface("GetItemAt", lambda out: items.invoke(8, (_DWORD, _PVOID), index, out)) as item:
                        paths.append(_path(item, ole))
                return tuple(paths)
    finally:
        ole.CoUninitialize()


def pick_dwg_files(title: str) -> tuple[str, ...]:
    return _pick(title, folder=False)


def pick_folder(title: str) -> str:
    result = _pick(title, folder=True)
    return result[0] if result else ""
