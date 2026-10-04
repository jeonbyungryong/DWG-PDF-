"""Strict PDF reading with an opt-in AutoCAD catalogue viewing-mode exception."""
from io import BytesIO
import re

from pypdf import PdfReader
from pypdf._utils import read_non_whitespace
from pypdf.errors import PdfReadError
from pypdf.generic import IndirectObject, NameObject, read_object

_VIEW_MODES = {"/UseNone", "/UseOutlines", "/UseThumbs", "/FullScreen", "/UseOC", "/UseAttachments"}


def _catalogue_without_duplicate_view_modes(data: bytes, reader: PdfReader) -> bytes:
    root = reader.trailer.raw_get("/Root")
    if not isinstance(root, IndirectObject):
        raise PdfReadError("catalogue must be an indirect object")
    try:
        offset = reader.xref[root.generation][root.idnum]
    except KeyError as error:
        raise PdfReadError("compressed catalogue is not eligible for compatibility") from error
    header = re.match(rb"\s*(\d+)\s+(\d+)\s+obj\b", data[offset:])
    if not header or (int(header[1]), int(header[2])) != (root.idnum, root.generation):
        raise PdfReadError("invalid catalogue object offset")
    stream = BytesIO(data)
    stream.seek(offset + header.end())
    if read_non_whitespace(stream) + stream.read(1) != b"<<":
        raise PdfReadError("catalogue is not a dictionary")
    seen = set()
    duplicates = []
    while True:
        first = read_non_whitespace(stream)
        if first == b">" and stream.read(1) == b">":
            break
        if not first:
            raise PdfReadError("unterminated catalogue")
        stream.seek(-1, 1)
        start = stream.tell()
        key = read_object(stream, reader)
        if not isinstance(key, NameObject):
            raise PdfReadError("invalid catalogue key")
        if not read_non_whitespace(stream):
            raise PdfReadError("missing catalogue value")
        stream.seek(-1, 1)
        value = read_object(stream, reader)
        if key == "/PageMode":
            if not isinstance(value, NameObject) or value not in _VIEW_MODES:
                raise PdfReadError("unknown catalogue viewing mode")
            if key in seen:
                duplicates.append((start, stream.tell()))
        elif key in seen:
            raise PdfReadError("duplicate catalogue key other than PageMode")
        seen.add(key)
    if not duplicates:
        raise PdfReadError("no duplicate catalogue viewing mode")
    copy = bytearray(data)
    for start, end in duplicates:
        # In-memory only. Same-length whitespace keeps every xref offset valid.
        copy[start:end] = b" " * (end - start)
    return bytes(copy)


def read_pdf(data: bytes, *, allow_duplicate_page_mode: bool = False) -> PdfReader:
    reader = PdfReader(BytesIO(data), strict=True)
    if not allow_duplicate_page_mode or reader.is_encrypted:
        return reader
    try:
        reader.root_object
    except PdfReadError as error:
        if not (str(error).startswith("Multiple definitions in dictionary at byte ")
                and str(error).endswith("for key /PageMode")):
            raise
        copy = _catalogue_without_duplicate_view_modes(data, reader)
        reader.stream.close()
        reader = PdfReader(BytesIO(copy), strict=True)
        reader.root_object
    return reader
