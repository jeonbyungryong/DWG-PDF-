"""Selection has no COM side effects; creation never falls back to another CAD."""
from .selection import CadCandidate, CadSelection
from ..errors import AppError



def resolve_selection(config, provider, prog_id, allow_experimental: bool) -> CadSelection:
    selected_provider = provider or config.cad_provider
    selected_id = prog_id
    if selected_id is None and selected_provider == config.cad_provider:
        selected_id = config.prog_id
    return CadSelection(selected_provider, selected_id,
                        allow_experimental or config.allow_experimental_autocad)


def create_session(candidate: CadCandidate):
    if candidate.provider == "autocad":
        from ..autocad.com_session import AutoCADSession
        return AutoCADSession(candidate)
    if candidate.provider == "gstarcad":
        from .com_session import ComSession
        from ..gstarcad.document import GstarDocument
        return ComSession(candidate, GstarDocument)
    raise AppError("E202", "unsupported CAD provider")
