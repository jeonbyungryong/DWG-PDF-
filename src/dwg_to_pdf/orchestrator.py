from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
import traceback
from typing import Any

from .batch_session import BatchSession
from .domain import ConversionOutcome, JobResult
from .errors import AppError


_REASONS = {
    "E203": "GstarCAD 문서 종료에 실패했습니다.",
    "E304": "도면 구조 매칭 결과가 모호합니다.",
    "E310": "승인된 템플릿 구조와 일치하지 않습니다.",
    "E311": "GstarCAD 배치 세션을 사용할 수 없습니다.",
    "E400": "원본 도면 보호 검증에 실패했습니다.",
    "E900": "예상하지 못한 변환 오류가 발생했습니다.",
}


def user_reason(error: AppError) -> str:
    message = str(error).casefold()
    if error.code == "E303":
        if "non-uniform" in message or "nonuniform" in message or "비균일" in message:
            return "비균일 블록 축척이 검출되었습니다."
        if "unsupported" in message or "지원하지 않는" in message:
            return "지원하지 않는 도면 변환이 검출되었습니다."
        if "automatic" in message or "auto" in message or "자동" in message:
            return "자동 템플릿 매칭을 수행할 수 없습니다."
        return "도면 축척 또는 구조를 자동으로 판별하지 못했습니다."
    if error.code == "E500":
        if _is_conflict_skip_message(error):
            return "PDF 출력 파일 충돌로 변환을 건너뛰었습니다."
        return "PDF 출력 처리에 실패했습니다."
    return _REASONS.get(error.code, str(error) or "변환에 실패했습니다.")


def _is_conflict_skip_message(error: AppError) -> bool:
    return error.code == "E500" and "existing pdf output was not replaced" in str(error).casefold()


def technical_detail(error: BaseException) -> str:
    """Keep raw message, chained exceptions, and exception notes for logs only."""

    parts: list[str] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = getattr(current, "code", None)
        prefix = f"{code}: " if code else ""
        parts.append(f"{prefix}{type(current).__name__}: {current}")
        notes = getattr(current, "__notes__", ())
        parts.extend(f"note: {note}" for note in notes)
        current = current.__cause__ or current.__context__
    return " | ".join(parts)


def _with_cleanup_detail(detail: str, batch: BatchSession) -> str:
    cleanup = batch.last_cleanup_error
    if cleanup is None:
        return detail
    return f"{detail} | session replacement: {technical_detail(cleanup)}"


def _user_facing_error(error: AppError) -> BaseException:
    """Recover the conversion-body exception wrapped by a document Close error."""

    has_body_failure = any(
        str(note).startswith("Primary failure:")
        for note in getattr(error, "__notes__", ())
    )
    if error.code == "E203" and has_body_failure and error.__cause__ is not None:
        return error.__cause__
    return error


def _failed_result(source: Path, error: AppError, batch: BatchSession, conflict_policy: str) -> JobResult:
    user_error = _user_facing_error(error)
    if isinstance(user_error, AppError):
        code = user_error.code
        reason = user_reason(user_error)
        skipped = _is_conflict_skip_message(user_error) and conflict_policy in {"ask", "skip"}
    else:
        code = "E900"
        reason = _REASONS["E900"]
        skipped = False
    return JobResult(
        source=source,
        status="skipped" if skipped else "failed",
        outputs=(),
        code=code,
        reason=reason,
        log_detail=_with_cleanup_detail(technical_detail(error), batch),
    )


def _unexpected_result(source: Path, error: Exception, batch: BatchSession) -> JobResult:
    detail = "".join(traceback.format_exception_only(type(error), error)).strip()
    return JobResult(
        source=source,
        status="failed",
        outputs=(),
        code="E900",
        reason=_REASONS["E900"],
        log_detail=_with_cleanup_detail(detail, batch),
    )


def run_jobs(
    service: Any,
    sources: Iterable[Path],
    output_dir: Path,
    conflict_policy: str,
    session_factory: Callable[[], Any],
) -> tuple[JobResult, ...]:
    """Convert a sequential batch, isolating ordinary failures per DWG."""

    ordered_sources = tuple(Path(source) for source in sources)
    batch = BatchSession(session_factory)
    try:
        batch.__enter__()
    except AppError as error:
        return tuple(
            JobResult(source, "failed", (), "E311", user_reason(AppError("E311", str(error))), technical_detail(error))
            for source in ordered_sources
        )

    results: list[JobResult] = []
    try:
        for source in ordered_sources:
            try:
                outcome: ConversionOutcome = batch.run_one(
                    lambda session, current=source: service.convert_in_session(
                        session, current, Path(output_dir), conflict_policy
                    )
                )
            except AppError as error:
                results.append(_failed_result(source, error, batch, conflict_policy))
            except Exception as error:
                results.append(_unexpected_result(source, error, batch))
            else:
                results.append(
                    JobResult(source, "success", tuple(frame.output for frame in outcome.frames))
                )
    finally:
        batch.__exit__(None, None, None)
    return tuple(results)
