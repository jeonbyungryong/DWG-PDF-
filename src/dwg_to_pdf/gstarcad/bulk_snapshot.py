"""Read-only CAD-side extraction; feed existing snapshot/transform validation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import uuid

from ..errors import AppError

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class NativeExtractionUnavailable(AppError):
    """A complete, identified CAD response permits safe legacy extraction."""
    def __init__(self, detail):
        super().__init__("E303", "CAD bulk extraction unavailable: " + str(detail))


class _Entity:
    def __init__(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("ObjectName"), str):
            raise AppError("E303", "invalid bulk entity")
        self._data = data

    def __getattr__(self, name):
        if name == "GetAttributes":
            return lambda: [_Entity(v) for v in self._data.get("Attributes", [])]
        if name == "GetBulge":
            return lambda index: self._data["Bulges"][index]
        if name not in self._data:
            raise AttributeError(name)
        value = self._data[name]
        if isinstance(value, dict) and "error" in value:
            raise AppError("E303", f"CAD bulk property {name} could not be read")
        return value


class _Collection:
    def __init__(self, items):
        self.items = items
        self.Count = len(items)

    def Item(self, key):
        return self.items[key]


class _Selection(_Collection):
    def Select(self, mode, point1, point2, filter_types, filter_data):
        from .document import _entity_type
        allowed = set(str(filter_data.value[0]).split(","))
        self.items = [item for item in self.items if _entity_type(item) in allowed]
        self.Count = len(self.items)
        # Crossing bounds were applied by the CAD-side query.

    def Delete(self):
        pass


class _Selections:
    def __init__(self, items):
        self.items = items

    def Item(self, name):
        raise KeyError(name)

    def Add(self, name):
        return _Selection(self.items)


def _path_key(value):
    return str(value).replace("\\", "/").casefold()


def parse_snapshot(text: str, token: str, document: str):
    try:
        if len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise ValueError("bulk response exceeded size limit")
        def reject_constant(value):
            raise ValueError(f"invalid JSON number: {value}")
        data = json.loads(text, parse_constant=reject_constant)
        if (type(data.get("version")) is not int or data["version"] != 1
                or data.get("token") != token or data.get("complete") is not True
                or _path_key(data.get("document")) != _path_key(document)):
            raise ValueError("bulk response identity or completion mismatch")
        if "error" in data:
            raise NativeExtractionUnavailable(data["error"])
        roots, blocks = data["entities"], data["blocks"]
        if not isinstance(roots, list) or not isinstance(blocks, dict):
            raise ValueError("invalid bulk collections")
        if len(blocks) > 2048 or len(roots) + sum(len(v) for v in blocks.values()) > 20000:
            raise ValueError("bulk extraction budget exceeded")
        entities = [_Entity(v) for v in roots]
        definitions = {}
        for name, values in blocks.items():
            if not isinstance(values, list):
                raise ValueError("invalid block collection")
            definitions[name] = _Collection([_Entity(v) for v in values])
        return SimpleNamespace(SelectionSets=_Selections(entities), Blocks=_Collection(definitions))
    except AppError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise AppError("E303", "invalid CAD bulk snapshot") from exc


def _lisp_string(value: str) -> str:
    # Only APP-controlled paths/tokens enter a command. Drawing text is data.
    if any(ord(c) < 32 for c in value):
        raise ValueError("control character in CAD command argument")
    return '"' + value.replace("\\", "/").replace('"', '\\"') + '"'


def extract_snapshot(raw, types=("TEXT", "MTEXT", "INSERT"), bounds=None, timeout=30.0):
    import pythoncom
    script = Path(__file__).with_name("bulk_extract.lsp").resolve(strict=True)
    expected_document = str(raw.FullName)
    token = uuid.uuid4().hex
    if not types or set(types) - {"TEXT", "MTEXT", "INSERT", "LINE", "LWPOLYLINE"}:
        raise ValueError("unsupported bulk filter")
    region = "nil"
    if bounds is not None:
        numbers = (bounds.lower_left.x, bounds.lower_left.y, bounds.upper_right.x, bounds.upper_right.y)
        import math
        if not all(math.isfinite(v) for v in numbers):
            raise AppError("E303", "invalid bulk query bounds")
        region = "'(" + " ".join(format(v, ".17g") for v in numbers) + ")"
    with tempfile.TemporaryDirectory(prefix="dwgpdf_bulk_") as folder:
        output = Path(folder) / "snapshot.json"
        command = (
            f'(progn (load {_lisp_string(str(script))}) '
            f'(dwgp:run {_lisp_string(str(output))} {_lisp_string(token)} '
            f'{_lisp_string(",".join(types))} {region}) (princ))\n'
        )
        raw.Activate()
        start = time.monotonic()
        raw.SendCommand(command)
        # SendCommand may be synchronous. This rejects late responses but is
        # not a watchdog capable of interrupting an unresponsive COM call.
        if time.monotonic() - start >= timeout:
            raise AppError("E303", "CAD bulk extraction timed out")
        while not output.exists():
            if time.monotonic() - start >= timeout:
                raise AppError("E303", "CAD bulk extraction timed out")
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)
        if output.stat().st_size > MAX_RESPONSE_BYTES:
            raise AppError("E303", "CAD bulk response exceeded size limit")
        payload = output.read_bytes()
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = payload.decode("mbcs")
        return parse_snapshot(text, token, expected_document)
