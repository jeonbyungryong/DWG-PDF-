"""Backward-compatible GstarCAD constructor over the shared session."""
from ..cad.com_session import ComSession, _gstar_pids
from ..cad.discovery import discover_candidates
from ..cad.selection import CadCandidate, CadSelection, select_candidate
from .document import GstarDocument


class GstarSession(ComSession):
    def __init__(self, prog_id: str) -> None:
        self.prog_id = prog_id
        super().__init__(None, GstarDocument)

    def _resolve_candidate(self) -> CadCandidate:
        return select_candidate(CadSelection("gstarcad", self.prog_id, False), discover_candidates("gstarcad"))
