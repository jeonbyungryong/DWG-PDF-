"""Compare decisions and rendered PDFs from two benchmark JSON results."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
from PIL import Image, ImageChops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    lookup = {x["source"]: x for x in after["outcomes"]}
    render_dir = args.output.parent / "render-comparison"
    render_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, old in enumerate(before["outcomes"]):
        new = lookup[old["source"]]
        if "error" in old or "error" in new:
            rows.append({"source": old["source"], "same_error": old.get("code") == new.get("code"), "before": old.get("error"), "after": new.get("error")})
            continue
        a, b = old["outcome"]["frames"][0], new["outcome"]["frames"][0]
        same_decision = all(a[key] == b[key] for key in ("scale", "rotation", "plot_window"))
        images = []
        for side, frame in (("before", a), ("after", b)):
            prefix = render_dir / f"{index}-{side}"
            subprocess.run(["pdftoppm", "-r", "144", "-png", "-singlefile", frame["output"], str(prefix)], check=True, capture_output=True)
            with Image.open(prefix.with_suffix(".png")) as im:
                images.append(im.convert("RGB"))
        same_pixels = images[0].size == images[1].size and ImageChops.difference(images[0], images[1]).getbbox() is None
        rows.append({"source": old["source"], "same_decision": same_decision, "same_pixels_144dpi": same_pixels, "before_seconds": old["seconds"], "after_seconds": new["seconds"]})
    timed = [x for x in rows if "before_seconds" in x]
    old_median = statistics.median(x["before_seconds"] for x in timed)
    new_median = statistics.median(x["after_seconds"] for x in timed)
    result = {"rows": rows, "before_median_seconds": old_median, "after_median_seconds": new_median, "median_reduction_percent": 100 * (1-new_median/old_median)}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return int(any(not row.get("same_error", row.get("same_decision") and row.get("same_pixels_144dpi")) for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
