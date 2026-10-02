from ..cad.com_session import ComSession
from ..cad.selection import CadCandidate
from ..errors import AppError


class AutoCADSession(ComSession):
    def __init__(self, candidate: CadCandidate) -> None:
        if candidate.provider != "autocad":
            raise AppError("E202", "AutoCAD session requires an AutoCAD candidate")
        def document_factory(raw):
            from .document import AutoCADDocument
            return AutoCADDocument(raw)
        super().__init__(candidate, document_factory)
