from pathlib import Path

from dwg_to_pdf.domain import JobResult
from dwg_to_pdf.result_presenter import build_result_report


def test_report_lists_each_failed_file_once_with_korean_reason() -> None:
    results = (
        JobResult(Path("good.dwg"), "success", (Path("good.pdf"),)),
        JobResult(
            Path("XXX-XXX.DWG"),
            "failed",
            (),
            "E303",
            "비균일 블록 축척이 검출되었습니다.",
        ),
        JobResult(Path("skip.dwg"), "skipped", (), "E500", "PDF 출력 파일 충돌로 변환을 건너뛰었습니다."),
    )

    report = build_result_report(results)

    assert (report.total, report.succeeded, report.failed, report.skipped) == (3, 1, 1, 1)
    assert report.failure_lines == (
        "XXX-XXX.DWG파일의 변환이 실패하였습니다(사유 : 비균일 블록 축척이 검출되었습니다.)",
    )
    assert report.summary_text.count("XXX-XXX.DWG파일") == 1


def test_report_uses_fallback_reason_and_keeps_results_immutable() -> None:
    result = JobResult(Path("unknown.dwg"), "failed", (), "E900")
    report = build_result_report((result,))
    assert report.failure_lines == ("unknown.dwg파일의 변환이 실패하였습니다(사유 : 변환에 실패했습니다.)",)
    assert report.results == (result,)
