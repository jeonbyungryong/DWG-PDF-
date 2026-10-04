from __future__ import annotations

from contextlib import AbstractContextManager
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
from types import TracebackType
from typing import Callable

from .errors import AppError
from .pdf_validator import PdfValidation, validate_pdf

_CLEANUP_ATTEMPTS = 4
_CLEANUP_INTERVAL_SEC = 0.05


def _resolve_path(path: Path, strict: bool) -> Path:
    return Path(path).resolve(strict=strict)


def _path_stat(path: Path):
    return path.stat()


def _path_lstat(path: Path):
    return path.lstat()


def _same_file(first: Path, second: Path) -> bool:
    return os.path.samefile(first, second)


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path)


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def _make_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _replace_file(source: Path, destination: Path) -> None:
    os.replace(source, destination)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _with_primary_detail(error: AppError, primary: BaseException) -> AppError:
    error.add_note(f"Primary failure: {type(primary).__name__}: {primary}")
    error.__cause__ = primary
    return error


def _verify_source_identity(
    source: Path,
    before_hash: str | None,
    before_mtime_ns: int | None,
) -> AppError | None:
    current_hash: str | None = None
    current_mtime_ns: int | None = None
    try:
        current_hash = sha256(source)
    except (OSError, AppError):
        pass
    try:
        current_mtime_ns = _path_stat(source).st_mtime_ns
    except OSError:
        pass
    changed = (
        before_hash is None
        or before_mtime_ns is None
        or current_hash != before_hash
        or current_mtime_ns != before_mtime_ns
    )
    if changed:
        return AppError("E400", "변환 중 원본 DWG가 변경되었습니다.", source)
    return None


def _with_cleanup_detail(error: AppError, cleanup_error: AppError) -> AppError:
    detail = f"Cleanup failure: {cleanup_error.code}: {cleanup_error}"
    if cleanup_error.path is not None:
        detail += f"; path={cleanup_error.path}"
    error.add_note(detail)
    return error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AppError("E400", "원본 DWG의 파일 신원을 확인할 수 없습니다.", path) from exc
    return digest.hexdigest().upper()


def _is_reparse_point(path: Path) -> bool:
    try:
        details = _path_lstat(path)
    except OSError as exc:
        raise AppError("E400", "DWG의 링크 또는 재분석 지점 상태를 확인할 수 없습니다.", path) from exc
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


class SourceWorkspace(AbstractContextManager["SourceWorkspace"]):
    """Owns one isolated writable copy while continuously protecting its source."""

    def __init__(self, source: Path, *, temp_root: Path | None = None) -> None:
        requested = Path(source)
        try:
            if _is_reparse_point(requested):
                raise AppError("E400", "링크 또는 재분석 지점 DWG는 처리할 수 없습니다.", requested)
            resolved = requested.resolve(strict=True)
        except AppError:
            raise
        except (OSError, RuntimeError) as exc:
            raise AppError("E400", "원본 DWG를 확인할 수 없습니다.", requested) from exc
        if not resolved.is_file() or resolved.suffix.casefold() != ".dwg":
            raise AppError("E400", "입력 파일은 일반 DWG 파일이어야 합니다.", resolved)
        self.source = resolved
        try:
            self._temp_root = _resolve_path(Path(temp_root), False) if temp_root is not None else None
        except (OSError, RuntimeError) as exc:
            raise AppError("E400", "임시 작업공간 루트를 확인할 수 없습니다.", requested) from exc
        self._temp_dir: Path | None = None
        self._copy: Path | None = None
        self._before_hash: str | None = None
        self._before_mtime_ns: int | None = None
        self._active = False

    def __enter__(self) -> "SourceWorkspace":
        if self._active or self._temp_dir is not None:
            raise AppError("E400", "임시 작업공간은 한 번만 사용할 수 있습니다.", self.source)
        self._before_hash = sha256(self.source)
        try:
            self._before_mtime_ns = _path_stat(self.source).st_mtime_ns
        except OSError as exc:
            raise AppError("E400", "원본 DWG의 수정시간을 확인할 수 없습니다.", self.source) from exc
        try:
            created = tempfile.mkdtemp(prefix="dwg-to-pdf-", dir=self._temp_root)
            self._temp_dir = _resolve_path(Path(created), True)
            self._copy = self._temp_dir / self.source.name
            shutil.copy2(self.source, self._copy)
            if _same_file(self.source, self._copy):
                raise AppError("E400", "원본과 임시 DWG가 동일한 파일입니다.", self.source)
            if sha256(self._copy) != self._before_hash:
                raise AppError("E400", "임시 DWG 복사본의 신원이 원본과 다릅니다.", self.source)
            self._active = True
            return self
        except AppError as primary:
            try:
                self._cleanup()
            except AppError as cleanup_error:
                raise _with_primary_detail(cleanup_error, primary)
            raise
        except (OSError, RuntimeError) as exc:
            primary = AppError("E400", "임시 DWG 작업공간을 만들 수 없습니다.", self.source)
            primary.__cause__ = exc
            try:
                self._cleanup()
            except AppError as cleanup_error:
                raise _with_primary_detail(cleanup_error, primary)
            raise primary

    def authorized_copy(self) -> Path:
        """Return the writable path only while this workspace is active."""

        if not self._active or self._temp_dir is None or self._copy is None:
            raise AppError("E400", "활성 임시 작업공간이 아닙니다.", self.source)
        try:
            copy = self._copy.resolve(strict=True)
            copy.relative_to(self._temp_dir)
        except (OSError, RuntimeError, ValueError) as exc:
            raise AppError("E400", "승인된 임시 DWG 복사본을 확인할 수 없습니다.", self.source) from exc
        if not copy.is_file() or copy.suffix.casefold() != ".dwg" or _is_reparse_point(copy):
            raise AppError("E400", "승인된 임시 DWG 복사본이 유효하지 않습니다.", self.source)
        try:
            if _same_file(self.source, copy):
                raise AppError("E400", "원본 DWG를 쓰기용으로 열 수 없습니다.", self.source)
        except AppError:
            raise
        except OSError as exc:
            raise AppError("E400", "원본과 임시 DWG의 파일 신원을 비교할 수 없습니다.", self.source) from exc
        return copy

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self._active = False
        cleanup_error: AppError | None = None
        try:
            self._cleanup()
        except AppError as error:
            cleanup_error = error

        identity_error = _verify_source_identity(
            self.source, self._before_hash, self._before_mtime_ns
        )
        if identity_error is not None:
            if cleanup_error is not None:
                _with_cleanup_detail(identity_error, cleanup_error)
            if exc is not None:
                raise _with_primary_detail(identity_error, exc)
            if cleanup_error is not None:
                raise identity_error from cleanup_error
            raise identity_error
        if cleanup_error is not None:
            if exc is not None:
                raise _with_primary_detail(cleanup_error, exc)
            raise cleanup_error
        return None

    def _cleanup(self) -> None:
        temp_dir = self._temp_dir
        self._active = False
        if temp_dir is None:
            self._copy = None
            return
        last_error: OSError | None = None
        for attempt in range(_CLEANUP_ATTEMPTS):
            try:
                _remove_tree(temp_dir)
                self._temp_dir = None
                self._copy = None
                return
            except FileNotFoundError:
                self._temp_dir = None
                self._copy = None
                return
            except OSError as exc:
                last_error = exc
                if attempt + 1 < _CLEANUP_ATTEMPTS:
                    _sleep(_CLEANUP_INTERVAL_SEC)
        raise AppError("E400", "임시 DWG 작업공간을 정리할 수 없습니다.", temp_dir) from last_error


def publish_pdf(temporary: Path, final: Path, *,
                validator: Callable[[Path], PdfValidation] | None = None) -> PdfValidation:
    """Validate and atomically publish a PDF; never damage an old final on failure."""

    requested_temporary = Path(temporary)
    requested_final = Path(final)
    owned_temporary = (
        requested_temporary.suffix.casefold() == ".pdf"
        and requested_temporary != requested_final
    )
    cleanup_temporary = requested_temporary
    resolved_temporary: Path | None = None
    primary_error: AppError | None = None
    result: PdfValidation | None = None
    try:
        if requested_temporary == requested_final:
            raise AppError("E420", "임시 PDF와 최종 PDF 경로가 같습니다.", requested_final)
        resolved_temporary = _resolve_path(requested_temporary, True)
        cleanup_temporary = resolved_temporary
        if resolved_temporary.suffix.casefold() != ".pdf":
            raise AppError("E420", "임시 PDF 출력 경로가 올바르지 않습니다.", resolved_temporary)
        owned_temporary = True
        resolved_final = _resolve_path(requested_final, False)
        if resolved_final.suffix.casefold() != ".pdf":
            raise AppError("E420", "최종 PDF 출력 경로가 올바르지 않습니다.", resolved_final)
        if resolved_temporary == resolved_final:
            owned_temporary = False
            raise AppError("E420", "임시 PDF와 최종 PDF 경로가 같습니다.", resolved_final)
        result = (validate_pdf if validator is None else validator)(resolved_temporary)
        try:
            _make_dir(resolved_final.parent)
            _replace_file(resolved_temporary, resolved_final)
        except OSError as exc:
            raise AppError("E421", "검증된 PDF를 최종 경로에 게시할 수 없습니다.", resolved_final) from exc
    except AppError as exc:
        primary_error = exc
    except (OSError, RuntimeError) as exc:
        primary_error = AppError("E420", "PDF 출력 경로를 확인할 수 없습니다.", requested_final)
        primary_error.__cause__ = exc
    finally:
        if owned_temporary:
            try:
                _remove_file(cleanup_temporary)
            except OSError as cleanup_exc:
                cleanup_error = AppError(
                    "E421", "임시 PDF 출력 파일을 정리할 수 없습니다.", cleanup_temporary
                )
                if primary_error is not None:
                    raise _with_primary_detail(cleanup_error, primary_error)
                raise cleanup_error from cleanup_exc
    if primary_error is not None:
        raise primary_error
    assert result is not None
    return result
