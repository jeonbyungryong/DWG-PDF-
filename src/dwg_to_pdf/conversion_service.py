from __future__ import annotations

from pathlib import Path
from typing import Literal
import uuid

from .configuration import AppConfig
from .conflict_resolver import resolve_collision
from .domain import ConvertedFrame, ConversionOutcome
from .errors import AppError
from .file_stability import require_stable
from .cad.contracts import CadSession
from .gstarcad.template_detector import DetectionLimits, detect_scale_cell, verify_rotation
from .output_planner import output_names
from .temp_workspace import SourceWorkspace, publish_pdf
from .templates.profile_store import ProfileStore
from .templates.structural_fallback import choose_profile_by_structure, profiles_for_scale_cell

ConflictPolicy = Literal["ask", "overwrite", "copy", "skip"]


def _remove_temporary(path: Path) -> None:
    path.unlink(missing_ok=True)


def _cleanup_temporary_after_failure(temporary: Path | None, primary: BaseException) -> None:
    """Remove only the one service-owned temporary PDF without hiding its primary error."""

    if temporary is None:
        return
    try:
        _remove_temporary(temporary)
    except OSError as cleanup_error:
        primary.add_note(
            f"Temporary PDF cleanup failure: {type(cleanup_error).__name__}: {cleanup_error}; "
            f"path={temporary}"
        )


def _resolve_source_after_stability(source: Path) -> Path:
    requested = Path(source)
    try:
        return requested.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AppError("E100", "could not resolve source DWG after stability check", requested) from exc


class ConversionService:
    """Convert one source through a caller-owned CAD session."""

    def __init__(self, config: AppConfig, profiles: ProfileStore) -> None:
        self.config = config
        self.profiles = profiles

    def convert_in_session(
        self,
        session: CadSession,
        source: Path,
        output_dir: Path,
        conflict_policy: ConflictPolicy,
    ) -> ConversionOutcome:
        if (
            not self.config.auto_match_enabled
            or self.config.matching_threshold is None
            or self.config.minimum_score_gap is None
        ):
            raise AppError("E303", "calibrated automatic matching is not enabled", Path(source))

        require_stable(Path(source))
        source_path = _resolve_source_after_stability(Path(source))
        final_base = Path(output_dir) / output_names(source_path, 1)[0]
        final_output = resolve_collision(final_base, conflict_policy)

        temporary: Path | None = None
        try:
            with SourceWorkspace(source_path) as workspace:
                with session.working_document(workspace) as document:
                    document.configure_extraction(self.config.use_native_extraction)
                    structural = {}
                    def resolve_missing_scale(provisional):
                        structural["decision"] = choose_profile_by_structure(
                            provisional, self.profiles.all(),
                            lambda profile, candidate: verify_rotation(document, profile, candidate),
                            self.config.matching_threshold, self.config.minimum_score_gap,
                        )
                        return structural["decision"]

                    cell = detect_scale_cell(
                        document, DetectionLimits(64, 5000), self.profiles.all(),
                        resolve_missing_scale,
                    )
                    matching_profiles = profiles_for_scale_cell(cell, self.profiles)
                    decision = structural.get("decision") or choose_profile_by_structure(
                        cell,
                        matching_profiles,
                        lambda profile, candidate: verify_rotation(document, profile, candidate),
                        self.config.matching_threshold,
                        self.config.minimum_score_gap,
                    )
                    profile = next(
                        (item for item in matching_profiles if item.profile_id == decision.candidate.profile_id),
                        None,
                    )
                    if profile is None:
                        raise AppError("E303", "chosen frame has no approved profile", source_path)
                    temporary = Path(output_dir) / f".{final_output.stem}.{uuid.uuid4().hex}.tmp.pdf"
                    document.plot_pdf(temporary, decision.candidate.plot_window,
                                      decision.candidate.rotation, self.config.preferred_media_names)
            publish_pdf(temporary, final_output)
        except Exception as primary:
            _cleanup_temporary_after_failure(temporary, primary)
            raise

        return ConversionOutcome(
            source_path,
            (
                ConvertedFrame(
                    final_output,
                    profile.scale,
                    decision.candidate.rotation,
                    decision.candidate.plot_window,
                ),
            ),
        )
