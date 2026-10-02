from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from collections.abc import Sequence

from dwg_to_pdf.calibration import choose_parameters
from dwg_to_pdf.errors import AppError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select zero-false-approval matcher calibration parameters.")
    parser.add_argument("labelled_json", type=Path)
    parser.add_argument("output_json", type=Path)
    return parser


def _publish(output: Path, selected: dict[str, float]) -> None:
    parent = output.parent
    if not parent.is_dir():
        raise AppError("E214", "calibration output directory does not exist", output)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=parent, prefix=f".{output.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(selected, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except (OSError, TypeError, ValueError) as exc:
        raise AppError("E214", f"could not atomically publish calibration: {exc}", output) from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        data = json.loads(args.labelled_json.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise AppError("E214", "labelled input must be a JSON array", args.labelled_json)
        _publish(args.output_json, choose_parameters(data))
    except (AppError, OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"calibration failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
