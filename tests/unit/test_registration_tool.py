from __future__ import annotations

from pathlib import Path

import pytest

from dwg_to_pdf.errors import AppError
import tools.register_reference_templates as registration
from tools.register_reference_templates import canonical_sources, publish_profile_set


def test_canonical_sources_requires_exactly_13_top_level_approved_scales(tmp_path: Path) -> None:
    names = ["1대1", "1대2", "1대5", "1대10", "1대20", "1대50", "1대100",
             "2대1", "5대1", "10대1", "20대1", "50대1", "100대1"]
    for name in names:
        (tmp_path / f"TEMPLETE_{name}.DWG").write_bytes(b"x")
    nested = tmp_path / "윈도우 영역 학습용"
    nested.mkdir()
    (nested / "TEMPLETE_1대1.DWG").write_bytes(b"target")

    found = canonical_sources(tmp_path)

    assert len(found) == 13
    assert all(path.parent == tmp_path for path in found)


def test_canonical_sources_rejects_missing_or_duplicate_scale(tmp_path: Path) -> None:
    (tmp_path / "TEMPLETE_1대1.DWG").write_bytes(b"x")
    with pytest.raises(AppError) as raised:
        canonical_sources(tmp_path)
    assert raised.value.code == "E308"


def test_atomic_directory_publish_rolls_back_byte_identical_prior_set_on_swap_failure(tmp_path: Path) -> None:
    output = tmp_path / "profiles"
    output.mkdir()
    (output / "old.json").write_bytes(b"old-set")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "new.json").write_bytes(b"new-set")
    real_replace = __import__("os").replace
    calls = 0

    def fail_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated new-set swap failure")
        return real_replace(source, destination)

    with pytest.raises(AppError):
        publish_profile_set(staging, output, replace=fail_second_replace)

    assert sorted(path.name for path in output.iterdir()) == ["old.json"]
    assert (output / "old.json").read_bytes() == b"old-set"
    assert not staging.exists()
    assert not list(tmp_path.glob("profiles.backup-*"))


def test_staging_directory_is_unique_sibling_created_by_path_mkdir(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "profiles"
    monkeypatch.setattr(
        registration.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: pytest.fail("tempfile.mkdtemp must not create profile staging"),
    )

    first = registration.create_staging_directory(output)
    second = registration.create_staging_directory(output)

    assert first.parent == output.parent
    assert second.parent == output.parent
    assert first != second
    assert first.is_dir() and second.is_dir()
