from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

Rotation = Literal[0, 90, 180, 270]
ScaleCellState = Literal["valid", "blank", "na"]


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
    scale_value_offset: Point
    scale_value_tolerance: float
    orientation_anchor: Point
    reference_window: Rect
    position_tolerance: float
    structural_signature: object | None = None


@dataclass(frozen=True)
class ScaleCandidate:
    anchor: Point
    token: str
    handle: str


@dataclass(frozen=True)
class ScaleCell:
    anchor: Point
    state: ScaleCellState
    token: str | None
    handle: str
    rotation_hint: Rotation | None = None


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
    reason: str | None = None
    log_detail: str | None = None


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
