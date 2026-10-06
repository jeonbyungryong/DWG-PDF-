"""Read-only approved-output audit; residual color policy must be explicit."""
import argparse
import json
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import ImageChops
from pypdf import PdfReader
import pypdfium2 as pdfium


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(summary, manifest, expected_count):
    expected = {case["file"]: case for case in manifest["cases"]}
    outcomes = summary["outcomes"]
    require(len(outcomes) == expected_count, "unexpected sample count")
    require(summary["sources_unchanged"] and summary["owned_pid_closed"] and summary["user_pids_preserved"], "protection failed")
    require(len({row["source"] for row in outcomes}) == expected_count, "duplicate samples")
    if expected_count == len(expected):
        require({row["source"] for row in outcomes} == set(expected), "wrong input corpus")
    rows = []
    for row in outcomes:
        require("error" not in row, "conversion failed")
        frame = row["outcome"]["frames"][0]
        require(len(row["outcome"]["frames"]) == 1, "unexpected frame count")
        case = expected[row["source"]]
        source = Path(row["outcome"]["source"])
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        require(source.name == case["file"] and source_hash == case["sha256"].upper(), "unapproved input hash")
        require(row["source_sha256"].upper() == source_hash, "input identity changed since benchmark")
        require(frame["scale"] == case["scale"] and frame["rotation"] == case["rotation"], "wrong scale or rotation")
        window = [frame["plot_window"][corner][axis] for corner, axis in
                  [("lower_left", "x"), ("lower_left", "y"), ("upper_right", "x"), ("upper_right", "y")]]
        require(max(abs(a - b) for a, b in zip(window, case["window"])) < .001, "wrong plot window")
        path = Path(frame["output"])
        data = path.read_bytes()
        reader = PdfReader(BytesIO(data), strict=True)
        require(not reader.is_encrypted and len(reader.pages) == 1, "invalid page structure")
        page = reader.pages[0]
        require(page.rotation == 0, "unexpected PDF rotation")
        width, height = float(page.mediabox.width) * 25.4 / 72, float(page.mediabox.height) * 25.4 / 72
        require(abs(width - 297) < .2 and abs(height - 210) < .2, "not A4 landscape")
        with pdfium.PdfDocument(data) as pdf:
            rendered_page = pdf[0]
            bitmap = rendered_page.render(scale=2)
            image = bitmap.to_pil().convert("RGB").copy()
            bitmap.close()
            rendered_page.close()
        red, green, blue = image.split()
        rg, rb = ImageChops.difference(red, green), ImageChops.difference(red, blue)
        chroma = max(rg.getextrema()[1], rb.getextrema()[1])
        gray = image.convert("L")
        dark = sum(gray.histogram()[:246])
        for item in (image, red, green, blue, rg, rb, gray):
            item.close()
        require(dark >= 8, "blank PDF")
        rows.append({"file": row["source"], "source_sha256": source_hash,
                     "pdf_sha256": hashlib.sha256(data).hexdigest().upper(),
                     "chroma_144dpi": chroma, "dark_pixels": dark})
    return {"audited": len(rows), "non_monochrome_pdfs": sum(row["chroma_144dpi"] != 0 for row in rows),
            "sources_unchanged": True, "user_pids_preserved": True, "owned_pid_closed": True,
            "full_43_audit": expected_count == 43 and len(expected) == 43, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("inputs-manifest.json"))
    parser.add_argument("--expected-count", type=int, default=43)
    parser.add_argument("--allow-residual-colors", action="store_true", help="MC-02 CTB-only acceptance; report colors without rejecting them")
    args = parser.parse_args()
    if not 1 <= args.expected_count <= 43:
        parser.error("expected count must be between 1 and 43")
    result = audit(json.loads(args.summary.read_text(encoding="utf-8")),
                   json.loads(args.manifest.read_text(encoding="utf-8")), args.expected_count)
    result["color_policy"] = "ctb_only_allow_residual" if args.allow_residual_colors else "strict_full_monochrome"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(not args.allow_residual_colors and result["non_monochrome_pdfs"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
