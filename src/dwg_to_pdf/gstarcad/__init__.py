"""Fail-closed GstarCAD COM inspection boundary."""

from .com_session import GstarSession
from .document import GstarDocument
from .template_detector import DetectionLimits, detect_scale_candidates, detect_scale_cell

__all__ = [
    "DetectionLimits",
    "GstarDocument",
    "GstarSession",
    "detect_scale_candidates",
    "detect_scale_cell",
]
