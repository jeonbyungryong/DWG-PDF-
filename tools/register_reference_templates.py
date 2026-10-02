from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from collections.abc import Callable

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.com_session import GstarSession
from dwg_to_pdf.templates.profile_store import ProfileStore
from dwg_to_pdf.templates.reference_registrar import extract_reference_snapshot, register_reference
from dwg_to_pdf.templates.scale_label import parse_reference_filename
from dwg_to_pdf.templates.scale_universe import APPROVED_SCALE_KEYS, scale_key


def canonical_sources(directory: Path) -> tuple[Path, ...]:
    sources = tuple(sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.casefold() == ".dwg"),
        key=lambda path: path.name.casefold(),
    ))
    by_key: dict[str, Path] = {}
    try:
        for source in sources:
            ratio = parse_reference_filename(source)
            key = scale_key(ratio.numerator, ratio.denominator)
            if key in by_key:
                raise AppError("E308", f"duplicate canonical reference scale: {key}")
            by_key[key] = source
    except AppError as exc:
        raise AppError("E308", "invalid canonical reference set", directory) from exc
    if set(by_key) != set(APPROVED_SCALE_KEYS) or len(sources) != 13:
        raise AppError("E308", "exactly 13 canonical top-level reference DWGs are required", directory)
    return tuple(by_key[key] for key in APPROVED_SCALE_KEYS)


def _identity(path: Path) -> tuple[str, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper(), path.stat().st_mtime_ns


def create_staging_directory(output: Path) -> Path:
    """Create a unique sibling with normal parent ACL inheritance."""

    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(16):
        staging = parent / f"{output.name}.staging-{uuid.uuid4().hex}"
        try:
            staging.mkdir()
        except FileExistsError:
            continue
        return staging
    raise AppError("E308", "could not create a unique profile staging directory", parent)


def publish_profile_set(
    staging: Path,
    output: Path,
    *,
    replace: Callable[[str | os.PathLike[str], str | os.PathLike[str]], None] = os.replace,
) -> None:
    """Publish a validated directory as one same-parent swap with rollback."""

    if staging.parent.resolve() != output.parent.resolve():
        raise AppError("E308", "profile staging and output must share one parent")
    backup = output.with_name(f"{output.name}.backup-{uuid.uuid4().hex}")
    had_prior = output.exists()
    try:
        if had_prior:
            replace(output, backup)
        try:
            replace(staging, output)
        except Exception as exc:
            if had_prior and backup.exists():
                try:
                    replace(backup, output)
                except Exception as rollback_exc:
                    raise AppError("E308", "profile-set swap and rollback both failed", output) from rollback_exc
            raise AppError("E308", "profile-set atomic swap failed", output) from exc
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if backup.exists() and output.exists():
            shutil.rmtree(backup, ignore_errors=True)
        if staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError as exc:
                raise AppError("E308", "profile staging cleanup failed", staging) from exc


def register_all(source_directory: Path, output_directory: Path, prog_id: str) -> list[dict[str, object]]:
    sources = canonical_sources(source_directory)
    before = {source: _identity(source) for source in sources}
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = create_staging_directory(output_directory)
    records: list[dict[str, object]] = []
    try:
        with GstarSession(prog_id) as session:
            for source in sources:
                try:
                    print(f"registering {source.name}", file=sys.stderr, flush=True)
                    document = session.open_readonly_copy(source)
                    snapshot = extract_reference_snapshot(
                        document, source, max_nested_blocks=64, max_nested_entities=5000
                    )
                    raw = register_reference(
                        snapshot, source, before[source][0], source_root=source_directory
                    )
                    destination = staging / f'{raw["profile_id"]}.json'
                    destination.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
                    records.append({
                        "source": str(source), "sha256": before[source][0],
                        "mtime_ns": before[source][1], "window": snapshot["reference_window"],
                        "scale_anchor": snapshot["scale_label_point"],
                        "scale_value_offset": raw["scale_value_offset"],
                        "signature_segments": len(raw["structural_signature"]["segments"]),
                        "owned_pid": session.owned_pid,
                    })
                finally:
                    session.close_document()

        store = ProfileStore(staging, source_root=source_directory)
        store.load_all()
        keys = {scale_key(item.scale.numerator, item.scale.denominator) for item in store.all()}
        if len(store.all()) != 13 or keys != set(APPROVED_SCALE_KEYS):
            raise AppError("E308", "generated profiles did not pass the canonical readiness gate")
        after = {source: _identity(source) for source in sources}
        if after != before:
            raise AppError("E203", "reference source identity changed during registration")

        publish_profile_set(staging, output_directory)
        return records
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register the 13 approved GstarCAD reference templates")
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--prog-id", default="GStarCAD.Application.26")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    records = register_all(args.source_directory, args.output_directory, args.prog_id)
    encoded = json.dumps(records, ensure_ascii=False, indent=2)
    if args.evidence:
        args.evidence.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
