# DWG to PDF Automatic Plot Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Windows console application that identifies each drawing frame from its internal Scale cell, reconstructs its plot window after arbitrary X/Y movement and 0°/90°/180°/270° rotation, and exports a validated A4 landscape PDF without modifying the source DWG.

**Architecture (superseded for batch/session lifecycle):** Pure Python modules own scale parsing, profile validation, rigid transforms, matching, output planning, and PDF validation. A narrow `gstarcad` adapter owns every COM object and uses server-side SelectionSet filters plus bounded nested-block traversal. Normal conversion uses one proven APP-owned GstarCAD process for a sequential batch, with one DWG open at a time; only a broken proven-owned session is replaced. The target DWG's saved Plot Window is logged but never used for matching or plotting. See [batch session and Scale fallback design](../specs/2026-07-16-batch-session-scale-fallback-design.md).

**Tech Stack:** Python 3.11+ 64-bit, standard-library dataclasses/TOML/logging/pathlib, pywin32, jsonschema, pypdf, pypdfium2, Pillow, pytest, PyInstaller onedir, GstarCAD 2026+ COM (`GStarCAD.Application.26`).

## Global Constraints

- Runtime platform is Windows 10/11 64-bit with GstarCAD 2026 or later.
- Runtime network access, online conversion, LLM calls, telemetry, and automatic dependency downloads are forbidden.
- The application is a local console program; no GUI automation or screen-coordinate clicking is permitted.
- The source DWG is never opened for write or saved; every plot operation uses a temporary copy and source SHA-256/mtime verification.
- One newly owned GstarCAD process handles a sequential batch with one work DWG open at a time; only a broken proven-owned session is replaced. User-owned GstarCAD processes are never attached to or terminated.
- ModelSpace full enumeration and Blocks collection full recursive enumeration are forbidden.
- Work-file names never participate in scale detection; only the internal Scale cell can approve a scale profile.
- The target DWG's saved Plot Window is diagnostic only and is never a candidate, fallback, or output window.
- Supported frame transforms are X/Y translation and rigid 0°/90°/180°/270° rotation; arbitrary uniform scale, non-uniform scale, mirror, and shear are rejected unless a separately approved profile explicitly allows mirror.
- Output is one-page A4 landscape, Fit to Paper, Center Plot, `DWG To PDF.pc3`, 297 × 210 mm media, `monochrome.ctb`, object lineweights and plot styles enabled.
- Small line/title-grid/TrueColor/CTB differences that are not human-visible do not block output; structural PDF, page, orientation, nonblank, Scale/profile, and frame-count checks do block output.
- Existing PDFs are never replaced without explicit user choice; validated output is committed atomically.
- Calibration values are numeric configuration values produced from labelled actual drawings; production auto-match remains disabled until the false-approval count is zero on both calibration and held-out validation sets.

---

## Planned File Map

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, Python floor, runtime/dev dependencies, console entry point |
| `config.example.toml` | Explicit timeouts, paths, matching state, plot requirements |
| `src/dwg_to_pdf/domain.py` | Immutable geometry, scale, profile, match, result data types |
| `src/dwg_to_pdf/errors.py` | Stable error codes and typed application exception |
| `src/dwg_to_pdf/configuration.py` | TOML loading and strict validation |
| `src/dwg_to_pdf/templates/scale_label.py` | Reference filename and internal Scale token parsing |
| `src/dwg_to_pdf/templates/profile_schema.py` | JSON Schema and dataclass conversion |
| `src/dwg_to_pdf/templates/profile_store.py` | Approved profile load, hash validation, deterministic lookup |
| `src/dwg_to_pdf/templates/plot_window_transform.py` | Four-way rigid transform and computed Window bounds |
| `src/dwg_to_pdf/templates/template_matcher.py` | Candidate validation, unique decision, deterministic ordering |
| `src/dwg_to_pdf/gstarcad/discovery.py` | GstarCAD/ProgID/process/environment discovery |
| `src/dwg_to_pdf/gstarcad/com_session.py` | Owned process lifecycle, mutex, timeouts, cleanup |
| `src/dwg_to_pdf/gstarcad/document.py` | Read-only snapshots and filtered SelectionSet operations |
| `src/dwg_to_pdf/gstarcad/media_resolver.py` | Exact PC3, A4-by-dimensions, and CTB preflight |
| `src/dwg_to_pdf/gstarcad/template_detector.py` | Scale candidates and bounded nested-block traversal |
| `src/dwg_to_pdf/gstarcad/plot_settings.py` | Exact PC3/media/CTB/Window/Fit/Center/rotation application |
| `src/dwg_to_pdf/gstarcad/plotter.py` | PlotToFile call and plot-stage timeout |
| `src/dwg_to_pdf/templates/reference_registrar.py` | Approved reference-template profile extraction |
| `src/dwg_to_pdf/input_resolver.py` | DWG/folder expansion and stable deterministic order |
| `src/dwg_to_pdf/file_stability.py` | Size/mtime stability and source identity checks |
| `src/dwg_to_pdf/temp_workspace.py` | Per-DWG temporary copy and cleanup |
| `src/dwg_to_pdf/output_planner.py` | PDF naming, frame ordering, collision plans |
| `src/dwg_to_pdf/conflict_resolver.py` | overwrite/copy/skip console decisions |
| `src/dwg_to_pdf/conversion_service.py` | Detection, computed Window plotting, PDF validation, atomic commit |
| `src/dwg_to_pdf/pdf_validator.py` | Header/parser/page/A4/render/nonblank validation |
| `src/dwg_to_pdf/orchestrator.py` | End-to-end sequencing without COM leakage |
| `src/dwg_to_pdf/cli.py`, `src/dwg_to_pdf/__main__.py` | CLI commands, exit codes, Korean summary |
| `tools/register_reference_templates.py` | Explicit profile registration utility |
| `tools/calibrate_matcher.py` | Labelled-set threshold/weight calibration |
| `packaging/dwg_to_pdf.spec`, `packaging/build.ps1` | Offline PyInstaller onedir build |
| `tests/unit/` | Pure deterministic tests |
| `tests/integration/` | Mock COM and opt-in real GstarCAD tests |
| `tests/fixtures/` | JSON snapshots and synthetic profile/candidate data |
| `docs/USER_GUIDE_KO.md`, `docs/TEST_REPORT.md` | Operator instructions and verified evidence |

---

### Task 1: Project Foundation, Domain Types, Errors, and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.toml`
- Create: `src/dwg_to_pdf/__init__.py`
- Create: `src/dwg_to_pdf/domain.py`
- Create: `src/dwg_to_pdf/errors.py`
- Create: `src/dwg_to_pdf/configuration.py`
- Test: `tests/unit/test_configuration.py`

**Interfaces:**
- Produces: `Point`, `Rect`, `ScaleRatio`, `Rotation`, `TemplateProfile`, `ScaleCandidate`, `FrameCandidate`, `MatchDecision`, `JobResult`.
- Produces: `AppError(code: str, message: str, path: Path | None)` and `load_config(path: Path) -> AppConfig`.
- Consumes: no application modules.

- [ ] **Step 1: Write the failing configuration and domain tests**

```python
# tests/unit/test_configuration.py
from decimal import Decimal
from pathlib import Path

import pytest

from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.domain import Point, Rect, ScaleRatio
from dwg_to_pdf.errors import AppError


def test_scale_ratio_returns_expected_a3_model_size() -> None:
    assert ScaleRatio(Decimal("1"), Decimal("50")).a3_model_size() == (
        Decimal("21000"), Decimal("14850")
    )


def test_rect_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError, match="rect bounds"):
        Rect(Point(10, 0), Point(0, 10))


def test_config_rejects_saved_target_window(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        '[gstarcad]\nprog_id="GStarCAD.Application.26"\n'
        '[matching]\nauto_match_enabled=false\nuse_target_saved_window=true\n'
        '[plot]\nplotter_name="DWG To PDF.pc3"\nmedia_width_mm=297.0\n'
        'media_height_mm=210.0\nstyle_sheet="monochrome.ctb"\n',
        encoding="utf-8",
    )
    with pytest.raises(AppError) as exc:
        load_config(path)
    assert exc.value.code == "E001"
```

- [ ] **Step 2: Run the tests and verify collection fails**

Run: `python -m pytest tests/unit/test_configuration.py -v`

Expected: FAIL during import because `dwg_to_pdf.configuration` and `dwg_to_pdf.domain` do not exist.

- [ ] **Step 3: Create the package metadata and minimal domain/config implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dwg-to-pdf"
version = "0.1.0"
requires-python = ">=3.11,<3.14"
dependencies = ["pywin32", "jsonschema", "pypdf", "pypdfium2", "Pillow"]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "pyinstaller", "pip-tools"]

[project.scripts]
dwg-to-pdf = "dwg_to_pdf.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers"
markers = ["gstarcad: requires an installed licensed GstarCAD"]
```

```python
# src/dwg_to_pdf/domain.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

Rotation = Literal[0, 90, 180, 270]


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Rect:
    lower_left: Point
    upper_right: Point

    def __post_init__(self) -> None:
        if self.lower_left.x >= self.upper_right.x or self.lower_left.y >= self.upper_right.y:
            raise ValueError("rect bounds must increase")

    @property
    def width(self) -> float:
        return self.upper_right.x - self.lower_left.x

    @property
    def height(self) -> float:
        return self.upper_right.y - self.lower_left.y


@dataclass(frozen=True)
class ScaleRatio:
    numerator: Decimal
    denominator: Decimal

    def __post_init__(self) -> None:
        if self.numerator <= 0 or self.denominator <= 0:
            raise ValueError("scale values must be positive")

    def a3_model_size(self) -> tuple[Decimal, Decimal]:
        factor = self.denominator / self.numerator
        return Decimal("420") * factor, Decimal("297") * factor


@dataclass(frozen=True)
class TemplateProfile:
    profile_id: str
    scale: ScaleRatio
    source_path: Path
    source_sha256: str
    approved: bool
    frame: Rect
    scale_anchor: Point
    orientation_anchor: Point
    reference_window: Rect
    position_tolerance: float


@dataclass(frozen=True)
class ScaleCandidate:
    anchor: Point
    token: str
    handle: str


@dataclass(frozen=True)
class FrameCandidate:
    profile_id: str
    scale_candidate: ScaleCandidate
    rotation: Rotation
    frame: Rect
    plot_window: Rect
    residual: float


@dataclass(frozen=True)
class MatchDecision:
    candidate: FrameCandidate
    score: float
    score_gap: float


@dataclass(frozen=True)
class JobResult:
    source: Path
    status: Literal["success", "failed", "held", "skipped"]
    outputs: tuple[Path, ...]
    code: str | None = None


@dataclass(frozen=True)
class ConvertedFrame:
    output: Path
    scale: ScaleRatio
    rotation: Rotation
    plot_window: Rect


@dataclass(frozen=True)
class ConversionOutcome:
    source: Path
    frames: tuple[ConvertedFrame, ...]
    used_target_saved_window: bool = False
```

```python
# src/dwg_to_pdf/errors.py
from pathlib import Path


class AppError(RuntimeError):
    def __init__(self, code: str, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
```

```python
# src/dwg_to_pdf/configuration.py
from dataclasses import dataclass
from pathlib import Path
import tomllib

from .errors import AppError


@dataclass(frozen=True)
class AppConfig:
    prog_id: str
    auto_match_enabled: bool
    plotter_name: str
    media_width_mm: float
    media_height_mm: float
    style_sheet: str
    preferred_media_names: tuple[str, ...]
    matching_threshold: float | None
    minimum_score_gap: float | None


def load_config(path: Path) -> AppConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    matching = data["matching"]
    if matching.get("use_target_saved_window", False):
        raise AppError("E001", "target saved Plot Window must remain disabled", path)
    enabled = bool(matching["auto_match_enabled"])
    threshold = matching.get("matching_threshold")
    gap = matching.get("minimum_score_gap")
    if enabled and (not isinstance(threshold, (int, float)) or not isinstance(gap, (int, float))):
        raise AppError("E001", "enabled auto-match requires numeric calibrated threshold and gap", path)
    plot = data["plot"]
    if (plot["media_width_mm"], plot["media_height_mm"]) != (297.0, 210.0):
        raise AppError("E001", "only A4 landscape 297 x 210 mm is allowed", path)
    return AppConfig(
        prog_id=data["gstarcad"]["prog_id"],
        auto_match_enabled=enabled,
        plotter_name=plot["plotter_name"],
        media_width_mm=float(plot["media_width_mm"]),
        media_height_mm=float(plot["media_height_mm"]),
        style_sheet=plot["style_sheet"],
        preferred_media_names=tuple(plot.get("preferred_media_names", ())),
        matching_threshold=float(threshold) if threshold is not None else None,
        minimum_score_gap=float(gap) if gap is not None else None,
    )
```

- [ ] **Step 4: Add the explicit example configuration**

```toml
# config.example.toml
[gstarcad]
prog_id = "GStarCAD.Application.26"
visible = false
open_timeout_sec = 120
detect_timeout_sec = 120
plot_timeout_sec = 180
shutdown_timeout_sec = 30

[matching]
auto_match_enabled = false
use_target_saved_window = false
allowed_rotations_deg = [0, 90, 180, 270]
allow_uniform_scale = false
allow_mirror = false
max_nested_blocks = 64
max_nested_entities = 5000

[plot]
plotter_name = "DWG To PDF.pc3"
media_width_mm = 297.0
media_height_mm = 210.0
style_sheet = "monochrome.ctb"
preferred_media_names = ["User77"]
fit_to_paper = true
center_plot = true
```

- [ ] **Step 5: Generate a hash-locked dependency file**

Run: `python -m piptools compile --generate-hashes --extra dev --output-file requirements.lock pyproject.toml`

Expected: `requirements.lock` contains exact versions and SHA-256 hashes for runtime, test, and packaging dependencies.

- [ ] **Step 6: Run the foundation tests**

Run: `python -m pytest tests/unit/test_configuration.py -v`

Expected: 3 passed.

- [ ] **Step 7: Commit the foundation**

```powershell
git add pyproject.toml requirements.lock config.example.toml src/dwg_to_pdf tests/unit/test_configuration.py
git commit -m "build: scaffold DWG to PDF core"
```

---

### Task 2: Scale Parsing and Approved Template Profiles

**Files:**
- Create: `src/dwg_to_pdf/templates/__init__.py`
- Create: `src/dwg_to_pdf/templates/scale_label.py`
- Create: `src/dwg_to_pdf/templates/profile_schema.py`
- Create: `src/dwg_to_pdf/templates/profile_store.py`
- Create: `tests/unit/test_scale_label.py`
- Create: `tests/unit/test_profile_store.py`
- Create: `tests/fixtures/profile_1_to_50.json`

**Interfaces:**
- Consumes: `ScaleRatio`, `Point`, `Rect`, `TemplateProfile`, `AppError` from Task 1.
- Produces: `parse_reference_filename(path: Path) -> ScaleRatio`, `parse_internal_scale(text: str) -> ScaleRatio`, `load_profile(path: Path) -> TemplateProfile`, `ProfileStore.find(scale: ScaleRatio) -> TemplateProfile`.

- [ ] **Step 1: Write parser and profile failure tests**

```python
# tests/unit/test_scale_label.py
from decimal import Decimal
from pathlib import Path
import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.scale_label import parse_internal_scale, parse_reference_filename


def test_reference_filename_and_internal_token_agree() -> None:
    expected = (Decimal("1"), Decimal("50"))
    ref = parse_reference_filename(Path("TEMPLETE_1대50.DWG"))
    internal = parse_internal_scale(" 1 : 50 ")
    assert (ref.numerator, ref.denominator) == expected
    assert internal == ref


def test_work_filename_is_not_a_valid_reference_name() -> None:
    with pytest.raises(AppError) as exc:
        parse_reference_filename(Path("XXX_1대50_PART.DWG"))
    assert exc.value.code == "E305"
```

```python
# tests/unit/test_profile_store.py
from pathlib import Path
import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.profile_store import ProfileStore


def test_unapproved_profile_is_rejected(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/profile_1_to_50.json").read_text(encoding="utf-8")
    (tmp_path / "profile.json").write_text(fixture.replace('"approved": true', '"approved": false'), encoding="utf-8")
    with pytest.raises(AppError) as exc:
        ProfileStore(tmp_path).load_all()
    assert exc.value.code == "E308"
```

- [ ] **Step 2: Run and verify missing modules fail**

Run: `python -m pytest tests/unit/test_scale_label.py tests/unit/test_profile_store.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement strict scale parsing**

```python
# src/dwg_to_pdf/templates/scale_label.py
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from ..domain import ScaleRatio
from ..errors import AppError

REFERENCE = re.compile(r"^(?:(?:TEMPLETE|TEMPLATE)_)?(?P<n>\d+(?:\.\d+)?)대(?P<d>\d+(?:\.\d+)?)$", re.I)
INTERNAL = re.compile(r"^\s*(?P<n>\d+(?:\.\d+)?)\s*(?::|대)\s*(?P<d>\d+(?:\.\d+)?)\s*$", re.I)


def _ratio(match: re.Match[str] | None, code: str, raw: str) -> ScaleRatio:
    if match is None:
        raise AppError(code, f"invalid scale token: {raw}")
    try:
        return ScaleRatio(Decimal(match.group("n")), Decimal(match.group("d")))
    except (InvalidOperation, ValueError) as exc:
        raise AppError(code, f"invalid scale token: {raw}") from exc


def parse_reference_filename(path: Path) -> ScaleRatio:
    return _ratio(REFERENCE.fullmatch(path.stem), "E305", path.name)


def parse_internal_scale(text: str) -> ScaleRatio:
    return _ratio(INTERNAL.fullmatch(text), "E303", text)
```

- [ ] **Step 4: Implement schema-backed profile loading**

```python
# src/dwg_to_pdf/templates/profile_schema.py
PROFILE_SCHEMA = {
    "type": "object",
    "required": ["profile_id", "scale", "source", "approved", "frame", "scale_anchor", "orientation_anchor", "reference_window", "position_tolerance"],
    "properties": {
        "profile_id": {"type": "string", "minLength": 1},
        "scale": {"type": "object", "required": ["numerator", "denominator"]},
        "source": {"type": "object", "required": ["path", "sha256"]},
        "approved": {"const": True},
        "frame": {"$ref": "#/$defs/rect"},
        "scale_anchor": {"$ref": "#/$defs/point"},
        "orientation_anchor": {"$ref": "#/$defs/point"},
        "reference_window": {"$ref": "#/$defs/rect"},
        "position_tolerance": {"type": "number", "exclusiveMinimum": 0},
    },
    "$defs": {
        "point": {"type": "array", "prefixItems": [{"type": "number"}, {"type": "number"}], "minItems": 2, "maxItems": 2},
        "rect": {"type": "array", "prefixItems": [{"$ref": "#/$defs/point"}, {"$ref": "#/$defs/point"}], "minItems": 2, "maxItems": 2},
    },
    "additionalProperties": False,
}
```

```python
# src/dwg_to_pdf/templates/profile_store.py
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from jsonschema import validate

from ..domain import Point, Rect, ScaleRatio, TemplateProfile
from ..errors import AppError
from .profile_schema import PROFILE_SCHEMA


def load_profile(path: Path) -> TemplateProfile:
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate(raw, PROFILE_SCHEMA)
    except Exception as exc:
        raise AppError("E308", f"invalid or unapproved profile: {path.name}", path) from exc
    point = lambda value: Point(float(value[0]), float(value[1]))
    rect = lambda value: Rect(point(value[0]), point(value[1]))
    return TemplateProfile(
        profile_id=raw["profile_id"],
        scale=ScaleRatio(Decimal(raw["scale"]["numerator"]), Decimal(raw["scale"]["denominator"])),
        source_path=Path(raw["source"]["path"]),
        source_sha256=raw["source"]["sha256"],
        approved=True,
        frame=rect(raw["frame"]),
        scale_anchor=point(raw["scale_anchor"]),
        orientation_anchor=point(raw["orientation_anchor"]),
        reference_window=rect(raw["reference_window"]),
        position_tolerance=float(raw["position_tolerance"]),
    )


class ProfileStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._profiles: dict[ScaleRatio, TemplateProfile] = {}

    def load_all(self) -> None:
        profiles = [load_profile(path) for path in sorted(self.directory.glob("*.json"))]
        for profile in profiles:
            if not profile.source_path.exists():
                raise AppError("E308", f"reference DWG is missing: {profile.source_path}", profile.source_path)
            actual = hashlib.sha256(profile.source_path.read_bytes()).hexdigest().upper()
            if actual != profile.source_sha256.upper():
                raise AppError("E308", f"reference DWG hash changed: {profile.source_path}", profile.source_path)
        self._profiles = {profile.scale: profile for profile in profiles}

    def find(self, scale: ScaleRatio) -> TemplateProfile:
        try:
            return self._profiles[scale]
        except KeyError as exc:
            raise AppError("E300", f"no approved profile for {scale}") from exc
```

- [ ] **Step 5: Add the deterministic 1:50 fixture and run tests**

```json
{
  "profile_id": "synthetic-a3-1-to-50-v1",
  "scale": {"numerator": "1", "denominator": "50"},
  "source": {"path": "tests/fixtures/synthetic_1_to_50.dwg", "sha256": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
  "approved": true,
  "frame": [[0.0, 0.0], [21000.0, 14850.0]],
  "scale_anchor": [19250.0, 850.0],
  "orientation_anchor": [20500.0, 1200.0],
  "reference_window": [[0.0, 0.0], [21000.0, 14850.0]],
  "position_tolerance": 5.0
}
```

Run: `python -m pytest tests/unit/test_scale_label.py tests/unit/test_profile_store.py -v`

Expected: 3 passed.

- [ ] **Step 6: Commit the scale/profile layer**

```powershell
git add src/dwg_to_pdf/templates tests/unit/test_scale_label.py tests/unit/test_profile_store.py tests/fixtures/profile_1_to_50.json
git commit -m "feat: add approved scale profiles"
```

---

### Task 3: Four-Direction Frame and Plot Window Geometry

**Files:**
- Create: `src/dwg_to_pdf/templates/plot_window_transform.py`
- Create: `src/dwg_to_pdf/templates/template_matcher.py`
- Create: `tests/unit/test_plot_window_transform.py`
- Create: `tests/unit/test_template_matcher.py`

**Interfaces:**
- Consumes: Task 1 domain types and Task 2 profiles.
- Produces: `compute_candidate(profile, scale_candidate, rotation) -> FrameCandidate`, `choose_unique(candidates, minimum_score, minimum_gap) -> MatchDecision`, `inverse_plot_rotation(frame_rotation) -> Rotation`.

- [ ] **Step 1: Write the translation and four-rotation tests**

```python
# tests/unit/test_plot_window_transform.py
import pytest

from dwg_to_pdf.domain import Point, ScaleCandidate
from dwg_to_pdf.templates.plot_window_transform import compute_candidate, inverse_plot_rotation
from dwg_to_pdf.templates.profile_store import load_profile
from pathlib import Path


@pytest.mark.parametrize(
    ("rotation", "anchor", "expected_size", "plot_rotation"),
    [
        (0, Point(29250, 20850), (21000, 14850), 0),
        (90, Point(-850, 29250), (14850, 21000), 270),
        (180, Point(-19250, -850), (21000, 14850), 180),
        (270, Point(850, -19250), (14850, 21000), 90),
    ],
)
def test_reconstructs_window_after_translation_and_rotation(rotation, anchor, expected_size, plot_rotation) -> None:
    profile = load_profile(Path("tests/fixtures/profile_1_to_50.json"))
    candidate = compute_candidate(profile, ScaleCandidate(anchor, "1:50", "A1"), rotation)
    assert (candidate.plot_window.width, candidate.plot_window.height) == pytest.approx(expected_size)
    assert inverse_plot_rotation(rotation) == plot_rotation
```

```python
# tests/unit/test_template_matcher.py
import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.templates.template_matcher import choose_unique


def test_ambiguous_rotation_is_held() -> None:
    with pytest.raises(AppError) as exc:
        choose_unique([(object(), 0.95), (object(), 0.94)], minimum_score=0.90, minimum_gap=0.02)
    assert exc.value.code == "E304"
```

- [ ] **Step 2: Run and verify geometry tests fail**

Run: `python -m pytest tests/unit/test_plot_window_transform.py tests/unit/test_template_matcher.py -v`

Expected: FAIL because the transform modules do not exist.

- [ ] **Step 3: Implement rigid rotation and computed Window bounds**

```python
# src/dwg_to_pdf/templates/plot_window_transform.py
from ..domain import FrameCandidate, Point, Rect, Rotation, ScaleCandidate, TemplateProfile


def rotate(point: Point, rotation: Rotation) -> Point:
    if rotation == 0:
        return point
    if rotation == 90:
        return Point(-point.y, point.x)
    if rotation == 180:
        return Point(-point.x, -point.y)
    return Point(point.y, -point.x)


def inverse_plot_rotation(frame_rotation: Rotation) -> Rotation:
    return {0: 0, 90: 270, 180: 180, 270: 90}[frame_rotation]  # type: ignore[return-value]


def _transform(point: Point, profile: TemplateProfile, target: Point, rotation: Rotation) -> Point:
    rotated_anchor = rotate(profile.scale_anchor, rotation)
    moved = rotate(point, rotation)
    return Point(moved.x + target.x - rotated_anchor.x, moved.y + target.y - rotated_anchor.y)


def _bounds(points: tuple[Point, ...]) -> Rect:
    return Rect(
        Point(min(p.x for p in points), min(p.y for p in points)),
        Point(max(p.x for p in points), max(p.y for p in points)),
    )


def compute_candidate(profile: TemplateProfile, scale_candidate: ScaleCandidate, rotation: Rotation) -> FrameCandidate:
    frame_points = (
        profile.frame.lower_left,
        Point(profile.frame.upper_right.x, profile.frame.lower_left.y),
        profile.frame.upper_right,
        Point(profile.frame.lower_left.x, profile.frame.upper_right.y),
    )
    window_points = (
        profile.reference_window.lower_left,
        Point(profile.reference_window.upper_right.x, profile.reference_window.lower_left.y),
        profile.reference_window.upper_right,
        Point(profile.reference_window.lower_left.x, profile.reference_window.upper_right.y),
    )
    return FrameCandidate(
        profile_id=profile.profile_id,
        scale_candidate=scale_candidate,
        rotation=rotation,
        frame=_bounds(tuple(_transform(p, profile, scale_candidate.anchor, rotation) for p in frame_points)),
        plot_window=_bounds(tuple(_transform(p, profile, scale_candidate.anchor, rotation) for p in window_points)),
        residual=0.0,
    )
```

- [ ] **Step 4: Implement unique candidate approval**

```python
# src/dwg_to_pdf/templates/template_matcher.py
from collections.abc import Sequence

from ..domain import FrameCandidate, MatchDecision
from ..errors import AppError


def choose_unique(candidates: Sequence[tuple[FrameCandidate, float]], minimum_score: float, minimum_gap: float) -> MatchDecision:
    if not candidates:
        raise AppError("E303", "no frame candidate matched")
    ranked = sorted(candidates, key=lambda item: (-item[1], item[0].scale_candidate.handle))
    if ranked[0][1] < minimum_score:
        raise AppError("E303", "best frame candidate is below the calibrated threshold")
    gap = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else 1.0
    if gap < minimum_gap:
        raise AppError("E304", "frame or rotation match is ambiguous")
    return MatchDecision(ranked[0][0], ranked[0][1], gap)
```

- [ ] **Step 5: Run geometry tests and the entire unit suite**

Run: `python -m pytest tests/unit/test_plot_window_transform.py tests/unit/test_template_matcher.py -v`

Expected: 5 passed.

Run: `python -m pytest tests/unit -v`

Expected: all unit tests pass.

- [ ] **Step 6: Commit the automatic Window geometry**

```powershell
git add src/dwg_to_pdf/templates/plot_window_transform.py src/dwg_to_pdf/templates/template_matcher.py tests/unit
git commit -m "feat: reconstruct plot windows for four rotations"
```

---

### Task 4: Owned GstarCAD Session and Filtered Drawing Inspection

**Files:**
- Create: `src/dwg_to_pdf/gstarcad/__init__.py`
- Create: `src/dwg_to_pdf/gstarcad/discovery.py`
- Create: `src/dwg_to_pdf/gstarcad/com_session.py`
- Create: `src/dwg_to_pdf/gstarcad/document.py`
- Create: `src/dwg_to_pdf/gstarcad/media_resolver.py`
- Create: `src/dwg_to_pdf/gstarcad/template_detector.py`
- Create: `tests/integration/test_com_contract.py`
- Create: `tests/unit/test_bounded_detector.py`

**Interfaces:**
- Consumes: domain/profile/parser interfaces from Tasks 1–3.
- Produces: `GstarSession.open_readonly_copy(path)`, `GstarDocument.filtered_snapshots(types, bounds)`, `detect_scale_candidates(document, limits) -> list[ScaleCandidate]`.
- Invariant: no `for entity in document.ModelSpace` and no `for block in document.Blocks` code path exists.

- [ ] **Step 1: Write a fake-COM contract test that forbids collection enumeration**

```python
# tests/unit/test_bounded_detector.py
from dataclasses import dataclass

from dwg_to_pdf.gstarcad.template_detector import DetectionLimits, detect_scale_candidates


class ExplodingCollection:
    def __iter__(self):
        raise AssertionError("full collection enumeration is forbidden")


@dataclass
class FakeDocument:
    ModelSpace = ExplodingCollection()
    Blocks = ExplodingCollection()

    def filtered_snapshots(self, types, bounds=None):
        return [
            {"type": "TEXT", "text": "Scale", "point": (100.0, 50.0), "handle": "10"},
            {"type": "TEXT", "text": "1:50", "point": (100.0, 40.0), "handle": "11"},
        ]


def test_detector_uses_only_filtered_snapshots() -> None:
    found = detect_scale_candidates(FakeDocument(), DetectionLimits(64, 5000))
    assert found[0].token == "1:50"
```

- [ ] **Step 2: Run and verify the detector test fails**

Run: `python -m pytest tests/unit/test_bounded_detector.py -v`

Expected: FAIL because `gstarcad.template_detector` does not exist.

- [ ] **Step 3: Implement ProgID discovery, filtered snapshots, and bounded Scale pairing**

```python
# src/dwg_to_pdf/gstarcad/discovery.py
import winreg

from ..errors import AppError


def require_registered_prog_id(prog_id: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\CLSID") as key:
            clsid, _ = winreg.QueryValueEx(key, None)
    except OSError as exc:
        raise AppError("E202", f"GstarCAD COM ProgID is not registered: {prog_id}") from exc
    if not str(clsid).strip():
        raise AppError("E202", f"GstarCAD COM ProgID has no CLSID: {prog_id}")
    return prog_id
```

```python
# src/dwg_to_pdf/gstarcad/media_resolver.py
from ..errors import AppError


def require_plot_environment(layout, preferred_names: tuple[str, ...], tolerance_mm: float = 0.20) -> str:
    devices = {str(name) for name in layout.GetPlotDeviceNames()}
    if "DWG To PDF.pc3" not in devices:
        raise AppError("E210", "DWG To PDF.pc3 is not installed")
    layout.ConfigName = "DWG To PDF.pc3"
    layout.RefreshPlotDeviceInfo()
    styles = {str(name).casefold() for name in layout.GetPlotStyleTableNames()}
    if "monochrome.ctb" not in styles:
        raise AppError("E212", "monochrome.ctb is not installed")
    matches = []
    for name in layout.GetCanonicalMediaNames():
        layout.CanonicalMediaName = name
        width, height = (float(value) for value in layout.GetPaperSize())
        if abs(width - 297.0) <= tolerance_mm and abs(height - 210.0) <= tolerance_mm:
            matches.append(str(name))
        elif abs(width - 210.0) <= tolerance_mm and abs(height - 297.0) <= tolerance_mm:
            matches.append(str(name))
    preferred = [name for name in preferred_names if name in matches]
    if len(preferred) == 1:
        return preferred[0]
    if len(matches) != 1:
        raise AppError("E211", f"expected one A4 media by dimensions, found {len(matches)}")
    return matches[0]
```

```python
# src/dwg_to_pdf/gstarcad/document.py
from dataclasses import dataclass
from typing import Any

from ..domain import Rect
from ..errors import AppError
from math import cos, sin

AC_SELECTION_SET_ALL = 5
AC_SELECTION_SET_CROSSING = 1


@dataclass
class GstarDocument:
    raw: Any

    def filtered_snapshots(self, types: tuple[str, ...], bounds: Rect | None = None) -> list[dict[str, object]]:
        name = "DWG_TO_PDF_FILTERED"
        try:
            self.raw.SelectionSets.Item(name).Delete()
        except Exception:
            pass
        selection = self.raw.SelectionSets.Add(name)
        filter_types = [0]
        filter_data = [",".join(types)]
        if bounds is None:
            selection.Select(AC_SELECTION_SET_ALL, None, None, filter_types, filter_data)
        else:
            selection.Select(
                AC_SELECTION_SET_CROSSING,
                (bounds.lower_left.x, bounds.lower_left.y, 0.0),
                (bounds.upper_right.x, bounds.upper_right.y, 0.0),
                filter_types,
                filter_data,
            )
        snapshots: list[dict[str, object]] = []
        for index in range(selection.Count):
            entity = selection.Item(index)
            object_name = str(entity.ObjectName).upper()
            dxf_type = "INSERT" if "BLOCKREFERENCE" in object_name else "MTEXT" if "MTEXT" in object_name else "TEXT" if "TEXT" in object_name or "ATTRIBUTE" in object_name else object_name
            point = getattr(entity, "InsertionPoint", None)
            if point is None:
                point = getattr(entity, "StartPoint", None)
            if point is None:
                coordinates = tuple(getattr(entity, "Coordinates", (0.0, 0.0)))
                point = (coordinates[0], coordinates[1], 0.0)
            snapshots.append({
                "type": dxf_type,
                "text": str(getattr(entity, "TextString", "")),
                "point": tuple(point)[:2],
                "handle": str(entity.Handle),
                "block_name": str(getattr(entity, "EffectiveName", getattr(entity, "Name", ""))),
                "rotation": float(getattr(entity, "Rotation", 0.0)),
                "x_scale": float(getattr(entity, "XScaleFactor", 1.0)),
                "y_scale": float(getattr(entity, "YScaleFactor", 1.0)),
            })
        selection.Delete()
        return snapshots

    def nested_text_snapshots(self, reference: dict[str, object], max_blocks: int, max_entities: int) -> list[dict[str, object]]:
        def ref_matrix(item) -> tuple[float, float, float, float, float, float]:
            angle = float(item.get("rotation", 0.0))
            sx, sy = float(item.get("x_scale", 1.0)), float(item.get("y_scale", 1.0))
            x, y = item.get("point", (0.0, 0.0))
            return (cos(angle) * sx, -sin(angle) * sy, sin(angle) * sx, cos(angle) * sy, float(x), float(y))

        def compose(parent, child):
            pa, pb, pc, pd, ptx, pty = parent
            ca, cb, cc, cd, ctx, cty = child
            return (
                pa * ca + pb * cc, pa * cb + pb * cd,
                pc * ca + pd * cc, pc * cb + pd * cd,
                pa * ctx + pb * cty + ptx, pc * ctx + pd * cty + pty,
            )

        def apply(matrix, point):
            a, b, c, d, tx, ty = matrix
            return (a * point[0] + b * point[1] + tx, c * point[0] + d * point[1] + ty)

        stack = [(str(reference["block_name"]), ref_matrix(reference))]
        visited: set[tuple[str, tuple[float, ...]]] = set()
        output: list[dict[str, object]] = []
        entity_count = 0
        while stack:
            name, matrix = stack.pop()
            key = (name, tuple(round(value, 9) for value in matrix))
            if key in visited:
                continue
            visited.add(key)
            if len(visited) > max_blocks:
                raise AppError("E303", "nested block traversal exceeded block limit")
            block = self.raw.Blocks.Item(name)
            for index in range(block.Count):
                entity_count += 1
                if entity_count > max_entities:
                    raise AppError("E303", "nested block traversal exceeded entity limit")
                entity = block.Item(index)
                object_name = str(entity.ObjectName).upper()
                point = tuple(getattr(entity, "InsertionPoint", (0.0, 0.0, 0.0)))[:2]
                if "BLOCKREFERENCE" in object_name:
                    child = {
                        "block_name": str(getattr(entity, "EffectiveName", entity.Name)), "point": point,
                        "rotation": float(getattr(entity, "Rotation", 0.0)),
                        "x_scale": float(getattr(entity, "XScaleFactor", 1.0)),
                        "y_scale": float(getattr(entity, "YScaleFactor", 1.0)),
                    }
                    stack.append((str(child["block_name"]), compose(matrix, ref_matrix(child))))
                elif "TEXT" in object_name:
                    output.append({"type": "MTEXT" if "MTEXT" in object_name else "TEXT", "text": str(entity.TextString), "point": apply(matrix, point), "handle": str(entity.Handle)})
        return output
```

```python
# src/dwg_to_pdf/gstarcad/template_detector.py
from dataclasses import dataclass

from ..domain import Point, ScaleCandidate
from ..templates.scale_label import parse_internal_scale


@dataclass(frozen=True)
class DetectionLimits:
    max_nested_blocks: int
    max_nested_entities: int


def detect_scale_candidates(document, limits: DetectionLimits) -> list[ScaleCandidate]:
    snapshots = document.filtered_snapshots(("TEXT", "MTEXT", "ATTRIB", "INSERT"))
    for reference in [item for item in snapshots if item.get("type") == "INSERT"]:
        snapshots.extend(document.nested_text_snapshots(reference, limits.max_nested_blocks, limits.max_nested_entities))
    labels = [item for item in snapshots if str(item.get("text", "")).strip().casefold() == "scale"]
    values = []
    for item in snapshots:
        try:
            parse_internal_scale(str(item.get("text", "")))
        except Exception:
            continue
        values.append(item)
    candidates: list[ScaleCandidate] = []
    for label in labels:
        lx, ly = label["point"]
        nearby = sorted(
            values,
            key=lambda item: (
                (item["point"][0] - lx) ** 2 + (item["point"][1] - ly) ** 2,
                str(item["handle"]),
            ),
        )
        if nearby:
            value = nearby[0]
            candidates.append(ScaleCandidate(Point(float(lx), float(ly)), str(value["text"]), str(label["handle"])))
    return candidates
```

- [ ] **Step 4: Implement owned COM session lifecycle with PID ownership**

```python
# src/dwg_to_pdf/gstarcad/com_session.py
from contextlib import AbstractContextManager
from pathlib import Path
import gc
import subprocess
import time
from typing import Any

import pythoncom
import win32com.client
import win32api
import win32event
import winerror

from ..errors import AppError
from .discovery import require_registered_prog_id
from .document import GstarDocument


class GstarSession(AbstractContextManager["GstarSession"]):
    def __init__(self, prog_id: str) -> None:
        self.prog_id = prog_id
        self.app: Any | None = None
        self.document: Any | None = None
        self.owned_pid: int | None = None
        self.mutex = None

    def __enter__(self) -> "GstarSession":
        self.mutex = win32event.CreateMutex(None, False, "Local\\DWG_TO_PDF_GSTARCAD_COM")
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            win32api.CloseHandle(self.mutex)
            self.mutex = None
            raise AppError("E201", "another DWG to PDF COM session is active")
        pythoncom.CoInitialize()
        require_registered_prog_id(self.prog_id)
        before = _gstar_pids()
        self.app = win32com.client.DispatchEx(self.prog_id)
        self.app.Visible = False
        after = _gstar_pids()
        created = sorted(after - before)
        if len(created) != 1:
            self._release()
            raise AppError("E201", "could not prove ownership of one GstarCAD process")
        self.owned_pid = created[0]
        return self

    def open_readonly_copy(self, path: Path) -> GstarDocument:
        if self.app is None:
            raise RuntimeError("session is not open")
        self.document = self.app.Documents.Open(str(path), True)
        return GstarDocument(self.document)

    def open_working_copy(self, path: Path) -> GstarDocument:
        if self.app is None:
            raise RuntimeError("session is not open")
        self.document = self.app.Documents.Open(str(path), False)
        return GstarDocument(self.document)

    def __exit__(self, exc_type, exc, tb) -> None:
        self._release()

    def _release(self) -> None:
        """Close COM, then wait/terminate only the exact captured process object.

        The production implementation captures a minimal-rights Windows process
        handle immediately after ownership proof. It never force-terminates by
        PID because a PID can be reused by a later user-owned GstarCAD process.
        If the exact handle cannot be acquired, shutdown is limited to COM
        Quit() and no forced termination is attempted.
        """
        ...
```

- [ ] **Step 5: Add real COM discovery contract test behind an opt-in marker**

```python
# tests/integration/test_com_contract.py
from pathlib import Path
import os
import pytest

from dwg_to_pdf.gstarcad.com_session import GstarSession


@pytest.mark.gstarcad
@pytest.mark.skipif("GSTARCAD_TEST_DWG" not in os.environ, reason="set GSTARCAD_TEST_DWG")
def test_opens_copy_in_owned_session_without_modelspace_iteration() -> None:
    with GstarSession("GStarCAD.Application.26") as session:
        document = session.open_readonly_copy(Path(os.environ["GSTARCAD_TEST_DWG"]))
        assert document.raw.ReadOnly is True
        assert document.filtered_snapshots(("TEXT", "MTEXT", "INSERT")) is not None
```

- [ ] **Step 6: Run mock tests, then the explicit real-COM smoke test**

Run: `python -m pytest tests/unit/test_bounded_detector.py -v`

Expected: 1 passed.

Run: `$env:GSTARCAD_TEST_DWG='D:\2026 PROJECT\APP 개발\DWG TO PDF 자동변환 프로그램\학습용 템플릿\윈도우 영역 학습용\TEMPLETE_1대1.DWG'; python -m pytest tests/integration/test_com_contract.py -m gstarcad -v`

Expected: 1 passed; the source SHA-256 remains `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0`.

- [ ] **Step 7: Commit the bounded COM inspection layer**

```powershell
git add src/dwg_to_pdf/gstarcad tests/unit/test_bounded_detector.py tests/integration/test_com_contract.py
git commit -m "feat: add owned filtered GstarCAD inspection"
```

---

### Task 5: Reference Registration and Rotation-Aware Candidate Verification

**Files:**
- Create: `src/dwg_to_pdf/templates/reference_registrar.py`
- Modify: `src/dwg_to_pdf/gstarcad/template_detector.py`
- Create: `tools/register_reference_templates.py`
- Create: `tests/unit/test_reference_registrar.py`
- Create: `tests/unit/test_saved_window_independence.py`

**Interfaces:**
- Consumes: filtered COM snapshots, scale parsing, profile schema, rigid transform.
- Produces: `extract_reference_snapshot(document, source) -> dict`, `register_reference(snapshot, source, sha256) -> dict`, `verify_rotation(document, profile, candidate) -> float`, and JSON files accepted by `ProfileStore`.

- [ ] **Step 1: Write registration and saved-Window-independence tests**

```python
# tests/unit/test_reference_registrar.py
from pathlib import Path

from dwg_to_pdf.templates.reference_registrar import register_reference


def test_registration_requires_filename_and_internal_scale_to_match() -> None:
    snapshot = {
        "frame": [[0, 0], [21000, 14850]],
        "scale_label_point": [19250, 850],
        "scale_value": "1:50",
        "orientation_anchor": [20500, 1200],
        "reference_window": [[0, 0], [21000, 14850]],
    }
    raw = register_reference(snapshot, Path("TEMPLETE_1대50.DWG"), "A" * 64)
    assert raw["scale"] == {"numerator": "1", "denominator": "50"}
    assert "target_saved_window" not in raw
```

```python
# tests/unit/test_saved_window_independence.py
from decimal import Decimal
from pathlib import Path
import pytest

from dwg_to_pdf.domain import Point, Rect, ScaleCandidate, ScaleRatio, TemplateProfile
from dwg_to_pdf.templates.plot_window_transform import compute_candidate


@pytest.mark.parametrize(
    ("ratio", "expected", "observed_saved"),
    [((1, 1), (420.0, 297.0), (148.08275862069, 98.3172413793104)),
     ((1, 50), (21000.0, 14850.0), (37280.0381465517, 31994.9784213362))],
)
def test_computed_window_does_not_accept_observed_saved_window(ratio, expected, observed_saved) -> None:
    width, height = expected
    profile = TemplateProfile(
        profile_id=f"a3-{ratio[0]}-to-{ratio[1]}-v1",
        scale=ScaleRatio(Decimal(ratio[0]), Decimal(ratio[1])),
        source_path=Path("reference.dwg"), source_sha256="A" * 64, approved=True,
        frame=Rect(Point(0, 0), Point(width, height)),
        scale_anchor=Point(width - 10, 10), orientation_anchor=Point(width - 5, 15),
        reference_window=Rect(Point(0, 0), Point(width, height)), position_tolerance=1.0,
    )
    result = compute_candidate(profile, ScaleCandidate(profile.scale_anchor, f"{ratio[0]}:{ratio[1]}", "1"), 0)
    assert (result.plot_window.width, result.plot_window.height) == pytest.approx(expected)
    assert (result.plot_window.width, result.plot_window.height) != pytest.approx(observed_saved)
```

- [ ] **Step 2: Run and verify tests fail for missing registration/service**

Run: `python -m pytest tests/unit/test_reference_registrar.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement deterministic reference registration**

```python
# src/dwg_to_pdf/templates/reference_registrar.py
from pathlib import Path

from ..errors import AppError
from .scale_label import parse_internal_scale, parse_reference_filename


def extract_reference_snapshot(document, source: Path) -> dict:
    ratio = parse_reference_filename(source)
    width, height = (float(value) for value in ratio.a3_model_size())
    snapshots = document.filtered_snapshots(("TEXT", "MTEXT", "ATTRIB", "INSERT"))
    for reference in [item for item in snapshots if item.get("type") == "INSERT"]:
        snapshots.extend(document.nested_text_snapshots(reference, 64, 5000))
    labels = [item for item in snapshots if str(item.get("text", "")).strip().casefold() == "scale"]
    if len(labels) != 1:
        raise AppError("E303", "reference must contain one filtered Scale label", source)
    label = labels[0]
    lx, ly = (float(value) for value in label["point"])
    values = []
    for item in snapshots:
        try:
            parsed = parse_internal_scale(str(item.get("text", "")))
        except AppError:
            continue
        x, y = (float(value) for value in item["point"])
        if y < ly:
            values.append((abs(x - lx) + abs(y - ly), parsed, item))
    if not values:
        raise AppError("E303", "reference Scale value was not found below Scale", source)
    _, internal, value = min(values, key=lambda item: (item[0], str(item[2]["handle"])))
    if internal != ratio:
        raise AppError("E305", "reference filename and internal Scale disagree", source)
    try:
        lower, upper = document.raw.ActiveLayout.GetWindowToPlot()
        lower_left = [float(lower[0]), float(lower[1])]
        upper_right = [float(upper[0]), float(upper[1])]
    except Exception as exc:
        raise AppError("E306", "approved reference Plot Window could not be read", source) from exc
    if abs((upper_right[0] - lower_left[0]) - width) > 0.001 * width or abs((upper_right[1] - lower_left[1]) - height) > 0.001 * height:
        raise AppError("E301", "approved reference Window does not match scale frame size", source)
    frame = [lower_left, upper_right]
    return {
        "frame": frame,
        "scale_label_point": [lx, ly],
        "scale_value": str(value["text"]),
        "orientation_anchor": lower_left,
        "reference_window": frame,
        "position_tolerance": 0.001 * max(width, height),
    }


def register_reference(snapshot: dict, source: Path, sha256: str) -> dict:
    filename_scale = parse_reference_filename(source)
    internal_scale = parse_internal_scale(str(snapshot["scale_value"]))
    if filename_scale != internal_scale:
        raise AppError("E305", "reference filename and internal Scale disagree", source)
    return {
        "profile_id": f"a3-{internal_scale.numerator}-to-{internal_scale.denominator}-v1",
        "scale": {"numerator": str(internal_scale.numerator), "denominator": str(internal_scale.denominator)},
        "source": {"path": str(source), "sha256": sha256},
        "approved": True,
        "frame": snapshot["frame"],
        "scale_anchor": snapshot["scale_label_point"],
        "orientation_anchor": snapshot["orientation_anchor"],
        "reference_window": snapshot["reference_window"],
        "position_tolerance": float(snapshot.get("position_tolerance", 0.001 * max(snapshot["frame"][1]))),
    }
```

- [ ] **Step 4: Implement candidate verification around predicted anchors only**

```python
# append to src/dwg_to_pdf/gstarcad/template_detector.py
from math import hypot

from ..domain import FrameCandidate, TemplateProfile
from ..templates.plot_window_transform import rotate


def verify_rotation(document, profile: TemplateProfile, candidate: FrameCandidate) -> float:
    expected = candidate.frame
    snapshots = document.filtered_snapshots(("INSERT", "LINE", "LWPOLYLINE"), expected)
    if not snapshots:
        return 0.0
    predicted = rotate(profile.orientation_anchor, candidate.rotation)
    anchor = candidate.scale_candidate.anchor
    scale_rotated = rotate(profile.scale_anchor, candidate.rotation)
    expected_orientation = (
        predicted.x + anchor.x - scale_rotated.x,
        predicted.y + anchor.y - scale_rotated.y,
    )
    distances = []
    for item in snapshots:
        x, y = item.get("point", (float("inf"), float("inf")))
        distances.append(hypot(x - expected_orientation[0], y - expected_orientation[1]))
    residual = min(distances, default=float("inf"))
    return max(0.0, 1.0 - residual / profile.position_tolerance)
```

- [ ] **Step 5: Add registration CLI and run unit tests**

```python
# tools/register_reference_templates.py
import argparse
import hashlib
import json
from pathlib import Path

from dwg_to_pdf.gstarcad.com_session import GstarSession
from dwg_to_pdf.templates.reference_registrar import extract_reference_snapshot, register_reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--prog-id", default="GStarCAD.Application.26")
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    sources = sorted(args.source_directory.glob("*.DWG"), key=lambda path: path.name.casefold())
    for source in sources:
        digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        with GstarSession(args.prog_id) as session:
            document = session.open_readonly_copy(source)
            snapshot = extract_reference_snapshot(document, source)
        raw = register_reference(snapshot, source, digest)
        output = args.output_directory / f'{raw["profile_id"]}.json'
        output.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run: `python -m pytest tests/unit/test_reference_registrar.py tests/unit/test_plot_window_transform.py -v`

Expected: all tests pass.

Run: `python tools/register_reference_templates.py "D:\2026 PROJECT\APP 개발\DWG TO PDF 자동변환 프로그램\학습용 템플릿" template_profiles`

Expected: exactly 13 approved JSON profiles are created, each filename/internal Scale agrees, and every source SHA-256 is recorded.

- [ ] **Step 6: Run the two supplied saved-Window regression tests**

Run: `python -m pytest tests/unit/test_saved_window_independence.py -v`

Expected: 2 passed; computed dimensions are 420 × 297 and 21,000 × 14,850, regardless of each file's saved Window.

- [ ] **Step 7: Commit registration and rotation-aware detection**

```powershell
git add src/dwg_to_pdf/templates/reference_registrar.py src/dwg_to_pdf/gstarcad/template_detector.py tools/register_reference_templates.py tests
git commit -m "feat: register anchors and detect rotated frames"
```

---

### Task 6: Exact Plot Settings, PDF Validation, and Source-Safe Atomic Output

**Files:**
- Create: `src/dwg_to_pdf/gstarcad/plot_settings.py`
- Create: `src/dwg_to_pdf/gstarcad/plotter.py`
- Create: `src/dwg_to_pdf/temp_workspace.py`
- Create: `src/dwg_to_pdf/pdf_validator.py`
- Create: `tests/unit/test_pdf_validator.py`
- Create: `tests/integration/test_plot_to_pdf.py`

**Interfaces:**
- Consumes: computed `FrameCandidate.plot_window`, `inverse_plot_rotation`, owned session.
- Produces: `apply_plot_settings(layout, window, frame_rotation, media_name)`, `plot_to_file(document, output)`, `validate_pdf(path) -> PdfValidation`, `SourceWorkspace`.

- [ ] **Step 1: Write PDF hard-gate tests**

```python
# tests/unit/test_pdf_validator.py
from pathlib import Path
import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.pdf_validator import validate_pdf


def test_blank_or_non_pdf_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(AppError) as exc:
        validate_pdf(path)
    assert exc.value.code == "E420"
```

- [ ] **Step 2: Run and verify validator test fails**

Run: `python -m pytest tests/unit/test_pdf_validator.py -v`

Expected: FAIL because `pdf_validator` does not exist.

- [ ] **Step 3: Implement explicit Window plot settings and inverse rotation mapping**

```python
# src/dwg_to_pdf/gstarcad/plot_settings.py
from typing import Any

from ..domain import Rect, Rotation
from ..templates.plot_window_transform import inverse_plot_rotation

AC_WINDOW = 4
AC_SCALE_TO_FIT = 0
PLOT_ROTATION_ENUM = {0: 0, 90: 1, 180: 2, 270: 3}


def apply_plot_settings(layout: Any, window: Rect, frame_rotation: Rotation, media_name: str) -> None:
    layout.ConfigName = "DWG To PDF.pc3"
    layout.CanonicalMediaName = media_name
    layout.PlotType = AC_WINDOW
    layout.SetWindowToPlot(
        (window.lower_left.x, window.lower_left.y),
        (window.upper_right.x, window.upper_right.y),
    )
    layout.UseStandardScale = True
    layout.StandardScale = AC_SCALE_TO_FIT
    layout.CenterPlot = True
    layout.StyleSheet = "monochrome.ctb"
    layout.PlotWithLineweights = True
    layout.PlotWithPlotStyles = True
    layout.PlotRotation = PLOT_ROTATION_ENUM[inverse_plot_rotation(frame_rotation)]
    layout.PlotHidden = False
    layout.PlotViewportBorders = False
    layout.PlotViewportsFirst = True
```

```python
# src/dwg_to_pdf/gstarcad/plotter.py
from pathlib import Path

from ..errors import AppError


def plot_to_file(document, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    document.SetVariable("BACKGROUNDPLOT", 0)
    try:
        ok = bool(document.Plot.PlotToFile(str(output)))
    except Exception as exc:
        raise AppError("E410", "GstarCAD PlotToFile failed", output) from exc
    if not ok or not output.exists():
        raise AppError("E410", "GstarCAD did not create the PDF", output)
```

- [ ] **Step 4: Implement source-safe temporary workspace**

```python
# src/dwg_to_pdf/temp_workspace.py
from contextlib import AbstractContextManager
import hashlib
from pathlib import Path
import shutil
import tempfile

from .errors import AppError


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


class SourceWorkspace(AbstractContextManager["SourceWorkspace"]):
    def __init__(self, source: Path) -> None:
        self.source = source
        self.before_hash = sha256(source)
        self.before_mtime = source.stat().st_mtime_ns
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dwg-to-pdf-"))
        self.copy = self.temp_dir / source.name

    def __enter__(self) -> "SourceWorkspace":
        shutil.copy2(self.source, self.copy)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if sha256(self.source) != self.before_hash or self.source.stat().st_mtime_ns != self.before_mtime:
            raise AppError("E400", "source DWG changed during conversion", self.source)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
```

- [ ] **Step 5: Implement PDF structural, A4, render, and nonblank validation**

```python
# src/dwg_to_pdf/pdf_validator.py
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader

from .errors import AppError


@dataclass(frozen=True)
class PdfValidation:
    page_count: int
    width_mm: float
    height_mm: float
    nonblank: bool


def validate_pdf(path: Path) -> PdfValidation:
    try:
        if not path.exists() or path.stat().st_size < 100 or not path.read_bytes()[:5].startswith(b"%PDF-"):
            raise ValueError("missing PDF header")
        reader = PdfReader(str(path))
        if len(reader.pages) != 1:
            raise ValueError("PDF must contain one page")
        box = reader.pages[0].mediabox
        width_mm = float(box.width) * 25.4 / 72.0
        height_mm = float(box.height) * 25.4 / 72.0
        if abs(width_mm - 297.0) > 0.2 or abs(height_mm - 210.0) > 0.2:
            raise ValueError("PDF is not A4 landscape")
        document = pdfium.PdfDocument(str(path))
        image = document[0].render(scale=1).to_pil().convert("L")
        nonblank = image.getextrema()[0] < 250
        if not nonblank:
            raise ValueError("PDF is blank")
        return PdfValidation(1, width_mm, height_mm, True)
    except Exception as exc:
        if isinstance(exc, AppError):
            raise
        raise AppError("E420", f"PDF validation failed: {exc}", path) from exc
```

- [ ] **Step 6: Add and run the plot-settings contract test**

```python
# tests/integration/test_plot_to_pdf.py
from dwg_to_pdf.domain import Point, Rect
from dwg_to_pdf.gstarcad.plot_settings import apply_plot_settings


class FakeLayout:
    def SetWindowToPlot(self, lower_left, upper_right) -> None:
        self.window = (lower_left, upper_right)


def test_computed_window_is_applied_and_saved_target_window_is_never_read() -> None:
    layout = FakeLayout()
    apply_plot_settings(layout, Rect(Point(100, 200), Point(520, 497)), 90, "User77")
    assert layout.window == ((100, 200), (520, 497))
    assert layout.ConfigName == "DWG To PDF.pc3"
    assert layout.CenterPlot is True
    assert layout.PlotRotation == 3
```

Run: `python -m pytest tests/unit/test_pdf_validator.py -v`

Expected: 1 passed.

Run: `python -m pytest tests/integration/test_plot_to_pdf.py -v`

Expected: 1 passed; the computed Window and inverse 270° plot rotation are applied without reading a saved target Window.

- [ ] **Step 7: Commit plotting, validation, and source protection**

```powershell
git add src/dwg_to_pdf/gstarcad/plot_settings.py src/dwg_to_pdf/gstarcad/plotter.py src/dwg_to_pdf/temp_workspace.py src/dwg_to_pdf/pdf_validator.py tests
git commit -m "feat: plot computed windows to validated PDFs"
```

---

### Task 7: Batch Planning, Conflicts, Orchestration, and CLI

**Files:**
- Create: `src/dwg_to_pdf/input_resolver.py`
- Create: `src/dwg_to_pdf/file_stability.py`
- Create: `src/dwg_to_pdf/output_planner.py`
- Create: `src/dwg_to_pdf/conflict_resolver.py`
- Create: `src/dwg_to_pdf/conversion_service.py`
- Create: `src/dwg_to_pdf/orchestrator.py`
- Create: `src/dwg_to_pdf/cli.py`
- Create: `src/dwg_to_pdf/__main__.py`
- Create: `tests/unit/test_output_planner.py`
- Create: `tests/integration/test_orchestrator.py`

**Interfaces:**
- Consumes: all prior public interfaces.
- Produces: `resolve_inputs(paths) -> tuple[Path, ...]`, `ConversionService.convert(source, output_dir, conflict_policy) -> ConversionOutcome`, `run_jobs(service, sources, output_dir, conflict_policy) -> tuple[JobResult, ...]`, `main(argv=None) -> int`.

- [ ] **Step 1: Write deterministic naming and collision tests**

```python
# tests/unit/test_output_planner.py
from pathlib import Path

from dwg_to_pdf.output_planner import next_copy_name, output_names


def test_multiple_frames_keep_source_name_without_scale_suffix() -> None:
    names = output_names(Path("XXX-XXXXA_PAD_UPR.DWG"), 3)
    assert names == ("XXX-XXXXA_PAD_UPR.pdf", "XXX-XXXXA_PAD_UPR_2.pdf", "XXX-XXXXA_PAD_UPR_3.pdf")


def test_copy_name_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "part.pdf").write_bytes(b"old")
    (tmp_path / "part - 복사본.pdf").write_bytes(b"old")
    assert next_copy_name(tmp_path / "part.pdf") == tmp_path / "part - 복사본 2.pdf"
```

- [ ] **Step 2: Run and verify output planning tests fail**

Run: `python -m pytest tests/unit/test_output_planner.py -v`

Expected: FAIL because `output_planner` does not exist.

- [ ] **Step 3: Implement deterministic output planning**

```python
# src/dwg_to_pdf/output_planner.py
from pathlib import Path


def output_names(source: Path, frame_count: int) -> tuple[str, ...]:
    if frame_count < 1:
        return ()
    names = [f"{source.stem}.pdf"]
    names.extend(f"{source.stem}_{index}.pdf" for index in range(2, frame_count + 1))
    return tuple(names)


def next_copy_name(path: Path) -> Path:
    first = path.with_name(f"{path.stem} - 복사본{path.suffix}")
    if not first.exists():
        return first
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem} - 복사본 {index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1
```

- [ ] **Step 4: Implement input resolution and stability check**

```python
# src/dwg_to_pdf/input_resolver.py
from pathlib import Path

from .errors import AppError


def resolve_inputs(paths: list[Path]) -> tuple[Path, ...]:
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(item.resolve() for item in path.iterdir() if item.is_file() and item.suffix.casefold() == ".dwg")
        elif path.is_file() and path.suffix.casefold() == ".dwg":
            found.add(path.resolve())
    if not found:
        raise AppError("E100", "no input DWG files")
    return tuple(sorted(found, key=lambda item: str(item).casefold()))
```

```python
# src/dwg_to_pdf/file_stability.py
from pathlib import Path
import time

from .errors import AppError


def require_stable(path: Path, interval_sec: float = 1.0) -> None:
    first = (path.stat().st_size, path.stat().st_mtime_ns)
    time.sleep(interval_sec)
    second = (path.stat().st_size, path.stat().st_mtime_ns)
    if first != second:
        raise AppError("E215", "DWG is still changing", path)
```

- [ ] **Step 5: Implement orchestration boundary and CLI exit codes**

```python
# src/dwg_to_pdf/conflict_resolver.py
from pathlib import Path
from typing import Literal

from .errors import AppError
from .output_planner import next_copy_name

ConflictPolicy = Literal["ask", "overwrite", "copy", "skip"]


def resolve_collision(path: Path, policy: ConflictPolicy) -> Path:
    if not path.exists():
        return path
    if policy == "ask":
        answer = input(f"기존 PDF 처리 [overwrite/copy/skip] {path.name}: ").strip().casefold()
        policy = {"overwrite": "overwrite", "copy": "copy", "skip": "skip"}.get(answer, "skip")
    if policy == "overwrite":
        return path
    if policy == "copy":
        return next_copy_name(path)
    raise AppError("E500", "existing PDF was not approved for replacement", path)
```

```python
# src/dwg_to_pdf/conversion_service.py
from pathlib import Path
import os

from .configuration import AppConfig
from .conflict_resolver import ConflictPolicy, resolve_collision
from .domain import ConvertedFrame, ConversionOutcome
from .errors import AppError
from .gstarcad.com_session import GstarSession
from .gstarcad.plot_settings import apply_plot_settings
from .gstarcad.plotter import plot_to_file
from .gstarcad.media_resolver import require_plot_environment
from .gstarcad.template_detector import DetectionLimits, detect_scale_candidates, verify_rotation
from .output_planner import output_names
from .pdf_validator import validate_pdf
from .temp_workspace import SourceWorkspace
from .templates.plot_window_transform import compute_candidate
from .templates.profile_store import ProfileStore
from .templates.scale_label import parse_internal_scale
from .templates.template_matcher import choose_unique


class ConversionService:
    def __init__(self, config: AppConfig, profiles: ProfileStore) -> None:
        self.config = config
        self.profiles = profiles

    def convert(self, source: Path, output_dir: Path, conflict_policy: ConflictPolicy) -> ConversionOutcome:
        if not self.config.auto_match_enabled or self.config.matching_threshold is None or self.config.minimum_score_gap is None:
            raise AppError("E303", "production auto-match is disabled until calibration is approved", source)
        output_dir.mkdir(parents=True, exist_ok=True)
        with SourceWorkspace(source) as workspace:
            with GstarSession(self.config.prog_id) as session:
                document = session.open_working_copy(workspace.copy)
                media_name = require_plot_environment(document.raw.ActiveLayout, self.config.preferred_media_names)
                scale_candidates = detect_scale_candidates(document, DetectionLimits(64, 5000))
                if not scale_candidates:
                    raise AppError("E303", "no internal Scale cell was detected", source)
                decisions = []
                for scale_candidate in scale_candidates:
                    profile = self.profiles.find(parse_internal_scale(scale_candidate.token))
                    scored = []
                    for rotation in (0, 90, 180, 270):
                        candidate = compute_candidate(profile, scale_candidate, rotation)
                        scored.append((candidate, verify_rotation(document, profile, candidate)))
                    decisions.append((choose_unique(scored, self.config.matching_threshold, self.config.minimum_score_gap), profile))
                decisions.sort(key=lambda item: (-item[0].candidate.frame.upper_right.y, item[0].candidate.frame.lower_left.x, item[0].candidate.scale_candidate.handle))
                names = output_names(source, len(decisions))
                converted = []
                for index, ((decision, profile), name) in enumerate(zip(decisions, names, strict=True), start=1):
                    candidate = decision.candidate
                    final = resolve_collision(output_dir / name, conflict_policy)
                    temporary_pdf = workspace.temp_dir / f"result-{index}.pdf"
                    apply_plot_settings(document.raw.ActiveLayout, candidate.plot_window, candidate.rotation, media_name)
                    plot_to_file(document.raw, temporary_pdf)
                    validate_pdf(temporary_pdf)
                    os.replace(temporary_pdf, final)
                    converted.append(ConvertedFrame(final, profile.scale, candidate.rotation, candidate.plot_window))
                return ConversionOutcome(source, tuple(converted), used_target_saved_window=False)
```

```python
# src/dwg_to_pdf/orchestrator.py
from pathlib import Path

from .domain import JobResult
from .file_stability import require_stable


def run_jobs(service, sources: tuple[Path, ...], output_dir: Path, conflict_policy: str) -> tuple[JobResult, ...]:
    results: list[JobResult] = []
    for source in sources:
        try:
            require_stable(source)
            outcome = service.convert(source, output_dir, conflict_policy)
            results.append(JobResult(source, "success", tuple(frame.output for frame in outcome.frames)))
        except Exception as exc:
            code = getattr(exc, "code", "E900")
            status = "skipped" if code == "E500" else "failed"
            results.append(JobResult(source, status, (), code))
    return tuple(results)
```

```python
# src/dwg_to_pdf/cli.py
import argparse
from pathlib import Path

from .configuration import load_config
from .conversion_service import ConversionService
from .input_resolver import resolve_inputs
from .orchestrator import run_jobs
from .templates.profile_store import ProfileStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dwg-to-pdf")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", default=Path("config.toml"), type=Path)
    parser.add_argument("--profiles", default=Path("template_profiles"), type=Path)
    parser.add_argument("--conflict", choices=("ask", "overwrite", "copy", "skip"), default="ask")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    sources = resolve_inputs(args.inputs)
    profiles = ProfileStore(args.profiles)
    profiles.load_all()
    results = run_jobs(ConversionService(config, profiles), sources, args.output, args.conflict)
    success = sum(result.status == "success" for result in results)
    print(f"완료 {success}개 / 전체 {len(results)}개")
    return 0 if success == len(results) else 1
```

```python
# tests/integration/test_orchestrator.py
from pathlib import Path

from dwg_to_pdf.domain import ConversionOutcome, ConvertedFrame, Point, Rect, ScaleRatio
from dwg_to_pdf.orchestrator import run_jobs
from decimal import Decimal


class FakeService:
    def convert(self, source, output_dir, conflict_policy):
        if source.name == "bad.dwg":
            raise RuntimeError("bad drawing")
        output = output_dir / f"{source.stem}.pdf"
        return ConversionOutcome(source, (ConvertedFrame(output, ScaleRatio(Decimal(1), Decimal(1)), 0, Rect(Point(0, 0), Point(420, 297))),))


def test_one_failed_dwg_does_not_stop_the_next(tmp_path: Path, monkeypatch) -> None:
    bad = tmp_path / "bad.dwg"
    good = tmp_path / "good.dwg"
    bad.write_bytes(b"bad")
    good.write_bytes(b"good")
    monkeypatch.setattr("dwg_to_pdf.orchestrator.require_stable", lambda path: None)
    results = run_jobs(FakeService(), (bad, good), tmp_path, "skip")
    assert [result.status for result in results] == ["failed", "success"]
```

```python
# src/dwg_to_pdf/__main__.py
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 6: Run unit and mock-orchestrator tests**

Run: `python -m pytest tests/unit/test_output_planner.py tests/integration/test_orchestrator.py -v`

Expected: all tests pass, including one failed DWG not stopping the next independent DWG.

- [ ] **Step 7: Commit batch and CLI behavior**

```powershell
git add src/dwg_to_pdf tests/unit/test_output_planner.py tests/integration/test_orchestrator.py
git commit -m "feat: add deterministic batch conversion CLI"
```

---

### Task 8: Calibration, Full Real-Drawing Regression, Packaging, and Documentation

**Files:**
- Create: `tools/calibrate_matcher.py`
- Create: `src/dwg_to_pdf/calibration.py`
- Create: `tests/unit/test_calibration.py`
- Create: `src/dwg_to_pdf/security_guard.py`
- Create: `src/dwg_to_pdf/dependency_audit.py`
- Create: `tests/unit/test_security_guard.py`
- Create: `tests/integration/test_actual_drawings.py`
- Create: `tests/integration/test_owned_process_cleanup.py`
- Create: `packaging/dwg_to_pdf.spec`
- Create: `packaging/build.ps1`
- Create: `packaging/verify_bundle.ps1`
- Create: `third_party/THIRD_PARTY_NOTICES.md`
- Create: `docs/USER_GUIDE_KO.md`
- Create: `docs/TEST_REPORT.md`
- Create: `README.md`

**Interfaces:**
- Consumes: the finished application.
- Produces: numeric approved matcher configuration, verified onedir bundle, final operator/test documentation.

- [ ] **Step 1: Write calibration behavior test**

```python
# tests/unit/test_calibration.py
from dwg_to_pdf.calibration import choose_parameters


def test_calibration_never_accepts_false_positive_configuration() -> None:
    candidates = [
        {"threshold": 0.90, "gap": 0.05, "false_approvals": 1, "correct_approvals": 20},
        {"threshold": 0.94, "gap": 0.08, "false_approvals": 0, "correct_approvals": 18},
    ]
    assert choose_parameters(candidates) == {"threshold": 0.94, "gap": 0.08}
```

- [ ] **Step 2: Implement zero-false-approval calibration selection**

```python
# src/dwg_to_pdf/calibration.py
def choose_parameters(candidates: list[dict]) -> dict[str, float]:
    safe = [item for item in candidates if item["false_approvals"] == 0]
    if not safe:
        raise ValueError("no zero-false-approval calibration exists")
    chosen = max(safe, key=lambda item: (item["correct_approvals"], item["gap"], item["threshold"]))
    return {"threshold": float(chosen["threshold"]), "gap": float(chosen["gap"])}
```

```python
# tools/calibrate_matcher.py
import argparse
import json
from pathlib import Path

from dwg_to_pdf.calibration import choose_parameters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labelled_results", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    candidates = json.loads(args.labelled_results.read_text(encoding="utf-8"))
    selected = choose_parameters(candidates)
    args.output.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run: `python -m pytest tests/unit/test_calibration.py -v`

Expected: 1 passed; the candidate with one false approval is rejected even though it has more correct approvals.

- [ ] **Step 3: Add the six-file real regression matrix**

```python
# src/dwg_to_pdf/security_guard.py
import ast
from pathlib import Path

from .errors import AppError

BANNED_NETWORK_IMPORTS = {"requests", "httpx", "aiohttp", "socket", "urllib.request"}


def audit_source_tree(package_root: Path) -> None:
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            else:
                continue
            if any(name in BANNED_NETWORK_IMPORTS for name in names):
                raise AppError("E214", f"network module import is forbidden: {path}")
```

```python
# src/dwg_to_pdf/dependency_audit.py
from pathlib import Path

from .errors import AppError


def require_hashed_lock(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required = ("pywin32", "jsonschema", "pypdf", "pypdfium2", "pillow")
    lowered = text.casefold()
    missing = [name for name in required if name not in lowered]
    if missing or "--hash=sha256:" not in lowered:
        raise AppError("E214", f"dependency lock is incomplete: {missing}", path)
```

```python
# tests/unit/test_security_guard.py
from pathlib import Path
import pytest

from dwg_to_pdf.dependency_audit import require_hashed_lock
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.security_guard import audit_source_tree


def test_network_import_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import requests\n", encoding="utf-8")
    with pytest.raises(AppError) as exc:
        audit_source_tree(tmp_path)
    assert exc.value.code == "E214"


def test_unhashed_lock_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "requirements.lock"
    path.write_text("pypdf==1\n", encoding="utf-8")
    with pytest.raises(AppError):
        require_hashed_lock(path)
```

```python
# tests/integration/test_actual_drawings.py
from pathlib import Path
import pytest

from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.pdf_validator import validate_pdf
from dwg_to_pdf.templates.profile_store import ProfileStore

CASES = [
    (r"D:\2026 PROJECT\SK ON\PAD\05.설계도면\02.설계도면(3D)\PART\변환 도면\XXX-XXXXA_GASKET_FRT.DWG", "1:5"),
    (r"D:\2026 PROJECT\SK ON\PAD\05.설계도면\02.설계도면(3D)\PART\변환 도면\XXX-XXXXA_Insualtion sheet UPR COVER B.DWG", "1:2"),
    (r"D:\2026 PROJECT\SK ON\PAD\05.설계도면\02.설계도면(3D)\PART\변환 도면\XXX-XXXXA_PAD_UPR.DWG", "1:10"),
    (r"D:\2026 PROJECT\SK ON\PAD\05.설계도면\02.설계도면(3D)\PART\변환 도면\XXX-XXXXA_Silicon Gromet A.DWG", "1:1"),
    (r"D:\2026 PROJECT\APP 개발\DWG TO PDF 자동변환 프로그램\학습용 템플릿\윈도우 영역 학습용\TEMPLETE_1대1.DWG", "1:1"),
    (r"D:\2026 PROJECT\APP 개발\DWG TO PDF 자동변환 프로그램\학습용 템플릿\윈도우 영역 학습용\TEMPLETE_1대50.DWG", "1:50"),
]


@pytest.mark.gstarcad
@pytest.mark.parametrize(("source", "scale"), CASES)
def test_actual_drawing_pipeline(source, scale, tmp_path: Path) -> None:
    profiles = ProfileStore(Path("template_profiles"))
    profiles.load_all()
    service = ConversionService(load_config(Path("config.toml")), profiles)
    result = service.convert(Path(source), tmp_path, "overwrite")
    expected_n, expected_d = scale.split(":")
    assert str(result.frames[0].scale.numerator) == expected_n
    assert str(result.frames[0].scale.denominator) == expected_d
    assert validate_pdf(result.frames[0].output).nonblank is True
    assert result.used_target_saved_window is False
```

- [ ] **Step 4: Run the complete automated suite and real regressions**

```python
# tests/integration/test_owned_process_cleanup.py
from dwg_to_pdf.gstarcad.com_session import GstarSession


class FakeApp:
    def Quit(self) -> None:
        return None


def test_cleanup_targets_only_the_exact_owned_process_handle(monkeypatch) -> None:
    terminated = []
    owned_handle = object()
    session = GstarSession("GStarCAD.Application.26")
    session.app = FakeApp()
    session.owned_pid = 22
    session._owned_process_handle = owned_handle
    monkeypatch.setattr("dwg_to_pdf.gstarcad.com_session._wait_for_process_exit", lambda handle: False)
    monkeypatch.setattr(
        "dwg_to_pdf.gstarcad.com_session._terminate_owned_process_handle",
        lambda handle: terminated.append(handle),
    )
    monkeypatch.setattr("dwg_to_pdf.gstarcad.com_session._close_process_handle", lambda handle: None)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.com_session.pythoncom.CoUninitialize", lambda: None)
    session._release()
    assert terminated == [owned_handle]
```

Run: `python -m pytest tests/unit -v --cov=dwg_to_pdf --cov-report=term-missing`

Expected: all unit tests pass; every safety-critical pure module is covered.

Run: `python -m pytest tests/integration -m "not gstarcad" -v`

Expected: all mock integration tests pass.

Run: `python -m pytest tests/integration -m gstarcad -v`

Expected: all six real files produce structurally valid, nonblank, one-page A4 landscape PDFs; source hashes and mtimes remain unchanged; no user-owned GstarCAD PID is terminated.

- [ ] **Step 5: Build the offline onedir bundle**

```powershell
# packaging/build.ps1
$ErrorActionPreference = 'Stop'
python -m pip install --require-hashes -r requirements.lock
$env:PYTHONPATH = 'src'
python -c "from pathlib import Path; from dwg_to_pdf.security_guard import audit_source_tree; audit_source_tree(Path('src/dwg_to_pdf'))"
python -c "from pathlib import Path; from dwg_to_pdf.dependency_audit import require_hashed_lock; require_hashed_lock(Path('requirements.lock'))"
python -m PyInstaller --noconfirm --clean packaging/dwg_to_pdf.spec
Get-FileHash -Algorithm SHA256 -Path dist/dwg-to-pdf/* | Sort-Object Path | Format-Table -AutoSize
```

```powershell
# packaging/verify_bundle.ps1
$ErrorActionPreference = 'Stop'
$exe = Resolve-Path 'dist\dwg-to-pdf\dwg-to-pdf.exe'
& $exe --help
if ($LASTEXITCODE -ne 0) { throw "bundled executable help failed: $LASTEXITCODE" }
$required = @(
  'dist\dwg-to-pdf\config.example.toml',
  'dist\dwg-to-pdf\third_party\THIRD_PARTY_NOTICES.md'
)
foreach ($path in $required) {
  if (-not (Test-Path -LiteralPath $path)) { throw "missing bundle file: $path" }
}
Get-ChildItem -File -Recurse -LiteralPath 'dist\dwg-to-pdf' |
  Get-FileHash -Algorithm SHA256 |
  Sort-Object Path |
  Export-Csv -NoTypeInformation -Encoding UTF8 'dist\dwg-to-pdf-checksums.csv'
```

```python
# packaging/dwg_to_pdf.spec
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("win32com") + collect_submodules("pypdfium2")
a = Analysis(
    ["src/dwg_to_pdf/__main__.py"],
    pathex=["src"],
    hiddenimports=hiddenimports,
    datas=[("config.example.toml", "."), ("template_profiles", "template_profiles"), ("third_party", "third_party")],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="dwg-to-pdf", console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="dwg-to-pdf")
```

Run: `powershell -ExecutionPolicy Bypass -File packaging/build.ps1`

Expected: `dist/dwg-to-pdf/dwg-to-pdf.exe` exists and no dependency download occurs when the built application runs.

Run: `powershell -ExecutionPolicy Bypass -File packaging/verify_bundle.ps1`

Expected: executable help succeeds, required configuration/notices exist, and `dist/dwg-to-pdf-checksums.csv` is created.

- [ ] **Step 6: Verify bundle behavior on a clean Windows account**

Run: `dist\dwg-to-pdf\dwg-to-pdf.exe --help`

Expected: exit code 0 without Python installed or network access.

Run: `dist\dwg-to-pdf\dwg-to-pdf.exe "D:\2026 PROJECT\APP 개발\DWG TO PDF 자동변환 프로그램\학습용 템플릿\윈도우 영역 학습용\TEMPLETE_1대1.DWG" --output "C:\Users\dknbtech\Documents\APP 개발\output\release-smoke" --config config.toml --profiles template_profiles --conflict overwrite`

Expected: validated A4 landscape PDF, Korean success summary, unchanged source hash/mtime, and only the owned GstarCAD process is closed.

- [ ] **Step 7: Write operator and test evidence documents**

```markdown
# DWG to PDF Test Report

| Case | Source SHA-256 before/after | Scale | Computed Window | Rotation | PDF A4 | Nonblank | Owned PID cleanup | Result |
|---|---|---|---|---|---|---|---|---|
| Window variation 1:1 | identical | 1:1 | 420 × 297 | detected | pass | pass | pass | pass |
| Window variation 1:50 | identical | 1:50 | 21,000 × 14,850 | detected | pass | pass | pass | pass |
```

```markdown
# DWG TO PDF 사용자 안내서

## 지원 입력
- 등록된 13개 축척 템플릿 규격
- 도곽 전체 X/Y 이동 및 0°·90°·180°·270° 회전

## 출력 원칙
- 대상 DWG의 기존 Plot Window는 사용하지 않습니다.
- 내부 Scale과 등록 Anchor로 새 Window를 계산합니다.
- 결과는 A4 가로 PDF이며 원본 DWG는 변경하지 않습니다.

## 실행
`dwg-to-pdf.exe "D:\도면\PART.DWG" --output "D:\도면\PDF" --config config.toml --profiles template_profiles`

## 기존 PDF
`overwrite`, `copy`, `skip` 중 사용자가 선택합니다. 승인 없는 덮어쓰기는 수행하지 않습니다.

## 보류 결과
E303·E304·E307·E309는 임의 출력하지 않았다는 의미입니다. 로그의 대상 파일, Scale 후보, 회전 후보, 조치 안내를 확인합니다.
```

```markdown
# Third-Party Notices

The release is built only from `requirements.lock`. Before distribution, copy every license file shipped in each locked wheel into `third_party/licenses/DISTRIBUTION_NAME/` and record its installed version and SHA-256 here. Release verification fails when a locked distribution has no recorded license.

`pypdfium2` and its bundled PDFium binary require the pypdfium2, PDFium, and transitive binary license files shipped by the selected wheel to be redistributed with the application.
```

```markdown
# DWG TO PDF

Local Windows console application for converting registered GstarCAD DWG drawing frames to validated A4 landscape PDFs. It detects scale from the internal Scale cell, ignores the work file's saved Plot Window, supports four rigid rotations, and never saves the source DWG.

See `docs/USER_GUIDE_KO.md` for operation and `docs/TEST_REPORT.md` for machine-verified release evidence.
```

- [ ] **Step 8: Final verification and release commit**

Run: `python -m pytest -v`

Expected: all non-hardware tests pass; GstarCAD-marked tests either pass on the development PC or are explicitly skipped only when the required environment variable is absent.

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intentional deliverables remain untracked.

```powershell
git add src tools tests packaging third_party docs README.md requirements.lock
git commit -m "feat: complete verified DWG to PDF application"
```

---

## Phase Gates

1. Tasks 1–3: pure scale/profile/window engine passes without GstarCAD.
2. Tasks 4–5: superseded by the single sequential APP-owned batch session rule; a broken proven-owned session may be replaced, while user-owned GstarCAD processes remain untouched. The two incorrect-saved-Window samples pass. See [batch session and Scale fallback design](../specs/2026-07-16-batch-session-scale-fallback-design.md).
3. Task 6: computed Window is applied through `SetWindowToPlot`, PDF validation passes, and source identity remains unchanged.
4. Task 7: multi-file names, ordering, conflicts, and independent failure handling pass.
5. Task 8: six supplied real files pass; then expand to the required labelled 20–30 drawing calibration/validation set before enabling production `auto_match_enabled`.
6. Packaging is accepted only after a Python-free, network-blocked Windows test and formal-license recheck.

The app must remain in dry-run/profile-registration mode if Gate 5 has not produced numeric zero-false-approval thresholds from both calibration and held-out validation drawings.
