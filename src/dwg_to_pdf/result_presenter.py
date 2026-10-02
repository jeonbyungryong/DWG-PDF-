from __future__ import annotations

from dataclasses import dataclass

from .domain import JobResult


@dataclass(frozen=True)
class ResultReport:
    results: tuple[JobResult, ...]
    total: int
    succeeded: int
    failed: int
    skipped: int
    failure_lines: tuple[str, ...]
    summary_text: str


def build_result_report(results: tuple[JobResult, ...]) -> ResultReport:
    """Build one final Korean result model; this module never shows a modal."""

    frozen_results = tuple(results)
    failure_lines = tuple(
        f"{result.source.name}파일의 변환이 실패하였습니다(사유 : {result.reason or '변환에 실패했습니다.'})"
        for result in frozen_results
        if result.status == "failed"
    )
    succeeded = sum(result.status == "success" for result in frozen_results)
    failed = sum(result.status == "failed" for result in frozen_results)
    skipped = sum(result.status == "skipped" for result in frozen_results)
    header = f"변환 결과: 전체 {len(frozen_results)}건 / 성공 {succeeded}건 / 실패 {failed}건 / 건너뜀 {skipped}건"
    summary_text = "\n".join((header, *failure_lines))
    return ResultReport(
        frozen_results,
        len(frozen_results),
        succeeded,
        failed,
        skipped,
        failure_lines,
        summary_text,
    )
