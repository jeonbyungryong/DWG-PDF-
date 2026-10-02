"""Small, testable wiring for opt-in actual-DWG release runs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .domain import JobResult
from .orchestrator import run_jobs
from .release_manifest import ActualDrawingCase


def run_release_cases(
    cases: Iterable[ActualDrawingCase],
    output_dir: Path,
    service: Any,
    conflict_policy: str,
    session_factory: Callable[[], Any],
) -> tuple[JobResult, ...]:
    """Preflight the release output location and convert every manifest case."""

    resolved_output = Path(output_dir)
    resolved_output.mkdir(parents=True, exist_ok=True)
    ordered_cases = tuple(cases)
    return run_jobs(
        service,
        (case.source for case in ordered_cases),
        resolved_output,
        conflict_policy,
        session_factory,
    )
