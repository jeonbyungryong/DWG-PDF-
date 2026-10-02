import json
from pathlib import Path

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.release_manifest import load_actual_cases


def _case(source: Path, scale: str = "1:1", **extra: object) -> dict[str, object]:
    return {"source": str(source), "expected_scale": scale, **extra}


def _write_manifest(tmp_path: Path, payload: object) -> Path:
    manifest = tmp_path / "actual-cases.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def _sources(tmp_path: Path, count: int = 6) -> list[Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    sources: list[Path] = []
    for number in range(count):
        source = (tmp_path / f"case-{number}.dwg").resolve()
        source.write_bytes(b"dwg")
        sources.append(source)
    return sources


def test_load_actual_cases_requires_six_existing_absolute_dwg_cases(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    manifest = _write_manifest(
        tmp_path,
        [_case(source, "1:5", label=f"case-{index}") for index, source in enumerate(sources)],
    )

    cases = load_actual_cases(manifest)

    assert [(case.source, case.expected_scale, case.label) for case in cases] == [
        (source, "1:5", f"case-{index}") for index, source in enumerate(sources)
    ]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{"source": "relative.dwg", "expected_scale": "1:1"}] * 6,
        [{"source": "C:/missing.dwg", "expected_scale": "1:1"}] * 6,
        [{"source": "C:/missing.txt", "expected_scale": "1:1"}] * 6,
        [{"source": "C:/missing.dwg", "expected_scale": "3:1"}] * 6,
        [{"source": "C:/missing.dwg", "expected_scale": "1:1", "unexpected": True}] * 6,
    ],
    ids=["too-few", "relative", "missing", "not-dwg", "unsupported-scale", "extra-field"],
)
def test_load_actual_cases_fails_closed_for_invalid_contract(tmp_path: Path, payload: object) -> None:
    manifest = _write_manifest(tmp_path, payload)

    with pytest.raises(AppError) as exc:
        load_actual_cases(manifest)

    assert exc.value.code == "E001"
    assert exc.value.path == manifest


def test_load_actual_cases_rejects_case_insensitive_duplicate_source(tmp_path: Path) -> None:
    source = _sources(tmp_path, 1)[0]
    distinct = _sources(tmp_path / "other", 5)
    duplicate = Path(str(source).swapcase())
    manifest = _write_manifest(
        tmp_path,
        [_case(source), _case(duplicate), *[_case(item) for item in distinct]],
    )

    with pytest.raises(AppError) as exc:
        load_actual_cases(manifest)

    assert exc.value.code == "E001"
    assert "duplicate" in str(exc.value).casefold()


def test_load_actual_cases_rejects_non_array_and_invalid_utf8(tmp_path: Path) -> None:
    non_array = _write_manifest(tmp_path, {"source": "x"})
    with pytest.raises(AppError) as exc:
        load_actual_cases(non_array)
    assert exc.value.code == "E001"

    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"\xff")
    with pytest.raises(AppError) as exc:
        load_actual_cases(invalid)
    assert exc.value.code == "E001"
