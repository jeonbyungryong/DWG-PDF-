from pathlib import Path

from dwg_to_pdf.release_harness import run_release_cases
from dwg_to_pdf.release_manifest import ActualDrawingCase


def test_release_harness_creates_output_directory_and_passes_every_manifest_case(monkeypatch, tmp_path: Path) -> None:
    cases = tuple(
        ActualDrawingCase((tmp_path / f"source-{number}.dwg").resolve(), "1:1")
        for number in range(7)
    )
    output_dir = tmp_path / "not-created" / "release-output"
    seen: dict[str, object] = {}
    sentinel = (object(),)

    def fake_run_jobs(service, sources, received_output_dir, policy, factory):
        seen["service"] = service
        seen["sources"] = tuple(sources)
        seen["output_dir"] = received_output_dir
        seen["policy"] = policy
        seen["factory"] = factory
        assert received_output_dir.is_dir()
        return sentinel

    monkeypatch.setattr("dwg_to_pdf.release_harness.run_jobs", fake_run_jobs)
    service = object()
    factory = object()

    result = run_release_cases(cases, output_dir, service, "overwrite", factory)

    assert result is sentinel
    assert seen == {
        "service": service,
        "sources": tuple(case.source for case in cases),
        "output_dir": output_dir,
        "policy": "overwrite",
        "factory": factory,
    }
