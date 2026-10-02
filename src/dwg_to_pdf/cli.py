from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from collections.abc import Sequence

from .configuration import load_config
from .errors import AppError
from .input_resolver import resolve_inputs
from .result_presenter import build_result_report
from .runtime_paths import default_config_path, default_profiles_path

# Keep --help and preflight import-safe in a frozen validation bundle. COM and
# pywin32 are only required when an actual conversion is requested.
ConversionService = None
GstarSession = None
run_jobs = None
ProfileStore = None
require_canonical_profiles = None


def _launch_desktop() -> int:
    from .desktop_launcher import run_desktop

    return run_desktop(main)


def _conversion_dependencies() -> tuple[object, object, object]:
    global ConversionService, GstarSession, run_jobs
    if run_jobs is None:
        from .conversion_service import ConversionService as service
        from .gstarcad.com_session import GstarSession as session
        from .orchestrator import run_jobs as jobs

        ConversionService, GstarSession, run_jobs = service, session, jobs
    return ConversionService, GstarSession, run_jobs


def _profile_dependencies() -> tuple[object, object]:
    global ProfileStore, require_canonical_profiles
    if ProfileStore is None or require_canonical_profiles is None:
        from .templates.profile_store import ProfileStore as store
        from .templates.profile_store import require_canonical_profiles as canonical

        ProfileStore, require_canonical_profiles = store, canonical
    return ProfileStore, require_canonical_profiles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="승인된 템플릿으로 DWG를 PDF로 변환합니다.")
    parser.add_argument("inputs", nargs="*", type=Path, help="DWG 파일 또는 DWG가 있는 폴더")
    parser.add_argument("--output", type=Path, help="PDF 출력 폴더")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="COM 서버를 시작하지 않고 동결 런타임 의존성과 기준 템플릿을 검사",
    )
    parser.add_argument("--config", default=default_config_path(), type=Path, help="설정 TOML 경로")
    parser.add_argument("--profiles", default=default_profiles_path(), type=Path, help="승인 프로파일 폴더")
    parser.add_argument(
        "--template-source-root",
        default=None,
        type=Path,
        help="프로파일의 기준 DWG가 있는 루트 폴더",
    )
    parser.add_argument(
        "--conflict",
        choices=("ask", "overwrite", "copy", "skip"),
        default="ask",
        help="동일한 PDF 파일이 존재할 때의 처리 방식",
    )
    return parser


def _prepare_output_dir(path: Path) -> Path:
    output = Path(path)
    try:
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir():
            raise OSError("output path is not a directory")
        if not os.access(output, os.W_OK):
            raise OSError("output directory is not writable")
        return output
    except OSError as exc:
        raise AppError("E001", f"could not prepare output directory: {output}", output) from exc


def _preflight(args: argparse.Namespace):
    store_type, canonical = _profile_dependencies()
    config = load_config(args.config)
    sources = resolve_inputs(args.inputs)
    source_root = args.template_source_root if args.template_source_root is not None else args.profiles
    profiles = store_type(args.profiles, source_root=source_root)
    profiles.load_all()
    canonical(profiles.all())
    output_dir = _prepare_output_dir(args.output)
    return config, sources, profiles, output_dir


def _initialization_error(error: BaseException) -> AppError:
    if isinstance(error, AppError):
        return error
    return AppError("E001", f"batch initialization failed: {error}")


def _run_self_check(args: argparse.Namespace) -> int:
    """Verify frozen defaults and COM Python imports without creating a COM server."""
    try:
        config_path = args.config
        profiles_path = args.profiles
        source_root = args.template_source_root if args.template_source_root is not None else profiles_path
        load_config(config_path)
        store_type, canonical = _profile_dependencies()
        profiles = store_type(profiles_path, source_root=source_root)
        profiles.load_all()
        canonical(profiles.all())
        _conversion_dependencies()
    except (AppError, OSError, ValueError, ImportError) as error:
        app_error = _initialization_error(error)
        print(f"런타임 자체 검사 실패 ({app_error.code}): {app_error}", file=sys.stderr)
        return 2
    print("RUNTIME_SELF_CHECK_OK")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.self_check:
        return _run_self_check(args)
    if not args.inputs or args.output is None:
        if not args.inputs and args.output is None:
            return _launch_desktop()
        parser.error("inputs and --output must be provided together")
    try:
        config, sources, profiles, output_dir = _preflight(args)
    except (AppError, OSError, ValueError) as error:
        app_error = _initialization_error(error)
        print(f"초기화 실패 ({app_error.code}): {app_error}", file=sys.stderr)
        return 2

    service_type, session_type, jobs = _conversion_dependencies()

    def session_factory():
        return session_type(config.prog_id)

    results = jobs(
        service_type(config, profiles),
        sources,
        output_dir,
        args.conflict,
        session_factory,
    )
    report = build_result_report(results)
    print(report.summary_text)
    return 0 if all(result.status == "success" for result in results) else 1
