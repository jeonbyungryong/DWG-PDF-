"""Native transport with read-only trust preflight; no security changes."""
from pathlib import Path

from ..cad import bulk_snapshot
from ..cad.bulk_snapshot import decode_payload, NativeExtractionUnavailable
from ..cad.diagnostics import emit


def _require_script_trust(raw) -> None:
    try:
        secure = raw.GetVariable("SECURELOAD")
        if type(secure) is not int or secure not in (0, 1, 2):
            raise ValueError("unknown secure loading policy")
        if secure == 0:
            return
        trusted = raw.GetVariable("TRUSTEDPATHS")
        if not isinstance(trusted, str):
            raise ValueError("unknown trusted path policy")
        script_directory = Path(bulk_snapshot.__file__).with_name("bulk_extract.lsp").resolve(strict=True).parent
        for entry in trusted.split(";"):
            entry = entry.strip().strip('"')
            recursive = entry.endswith(("\\...", "/..."))
            if recursive:
                entry = entry[:-3]
            directory = Path(entry)
            if not entry or not directory.is_absolute():
                continue
            try:
                directory = directory.resolve(strict=True)
            except OSError:
                continue
            if directory == script_directory or (recursive and directory in script_directory.parents):
                return
    except Exception as error:
        emit("native_fallback", "E303")
        raise NativeExtractionUnavailable("AutoCAD LISP trust policy could not be verified; using COM") from error
    emit("native_fallback", "E303")
    raise NativeExtractionUnavailable("bundled LISP is not explicitly trusted; using COM")


def extract_snapshot(raw, types=("TEXT", "MTEXT", "INSERT"), bounds=None, timeout=30.0):
    _require_script_trust(raw)
    return bulk_snapshot.extract_snapshot(raw, types, bounds, timeout, decoder=decode_payload)
