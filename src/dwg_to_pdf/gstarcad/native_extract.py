from ..cad import bulk_snapshot


def extract_snapshot(raw, types=("TEXT", "MTEXT", "INSERT"), bounds=None, timeout=30.0):
    return bulk_snapshot.extract_snapshot(raw, types, bounds, timeout, decoder=bulk_snapshot.decode_payload)
