"""Experimental transport; no SECURELOAD/TRUSTEDPATHS changes or retries."""
from ..cad import bulk_snapshot
from ..cad.bulk_snapshot import decode_payload


def extract_snapshot(raw, types=("TEXT", "MTEXT", "INSERT"), bounds=None, timeout=30.0):
    return bulk_snapshot.extract_snapshot(raw, types, bounds, timeout, decoder=decode_payload)
