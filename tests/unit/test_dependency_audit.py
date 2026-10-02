from __future__ import annotations

from pathlib import Path

import pytest

from dwg_to_pdf.dependency_audit import require_hashed_lock
from dwg_to_pdf.errors import AppError


REQUIRED = ("pywin32", "jsonschema", "pypdf", "pypdfium2", "pillow")
HASH = "a" * 64
CONTINUATION = " " + "\\" + "\n"


def _valid_lock() -> str:
    def block(name: str) -> str:
        return f"{name}==1.0" + CONTINUATION + f"    --hash=sha256:{HASH}"

    return "\n".join(block(name) for name in REQUIRED) + "\n"


def _assert_e214(path: Path) -> None:
    with pytest.raises(AppError) as raised:
        require_hashed_lock(path)
    assert raised.value.code == "E214"


def test_require_hashed_lock_accepts_a_hash_in_each_required_distribution_block(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(_valid_lock(), encoding="utf-8")

    require_hashed_lock(lock)


@pytest.mark.parametrize("missing", REQUIRED)
def test_require_hashed_lock_rejects_missing_required_distribution(tmp_path: Path, missing: str) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("\n".join(line for line in _valid_lock().splitlines() if not line.startswith(f"{missing}==")), encoding="utf-8")

    _assert_e214(lock)


def test_require_hashed_lock_rejects_global_hash_and_similar_distribution_names(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        _valid_lock().replace("pywin32==1.0", "pywin32-ctypes==1.0").replace("pypdf==1.0", "pypdf-extra==1.0"),
        encoding="utf-8",
    )

    _assert_e214(lock)


def test_require_hashed_lock_rejects_unpinned_required_distribution(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(_valid_lock().replace("pypdf==1.0", "pypdf>=1.0"), encoding="utf-8")

    _assert_e214(lock)


def test_require_hashed_lock_does_not_assign_a_hash_after_an_unrecognized_block_to_pypdf(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    marker = "pypdf==1.0" + CONTINUATION
    unrelated = "unrelated>=1\n    --hash=sha256:" + HASH
    lock.write_text(_valid_lock().replace(marker + "    --hash=sha256:" + HASH, marker + unrelated), encoding="utf-8")

    _assert_e214(lock)


def test_require_hashed_lock_rejects_hash_after_a_noncontinuation_required_line(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        _valid_lock().replace("pypdf==1.0" + CONTINUATION, "pypdf==1.0\n"),
        encoding="utf-8",
    )

    _assert_e214(lock)


@pytest.mark.parametrize("separator", ["\n", "\n# unexpected continuation comment\n"])
def test_require_hashed_lock_rejects_a_blank_or_unexpected_line_inside_a_required_continuation(tmp_path: Path, separator: str) -> None:
    lock = tmp_path / "requirements.lock"
    marker = "pypdf==1.0" + CONTINUATION
    lock.write_text(_valid_lock().replace(marker, marker + separator), encoding="utf-8")

    _assert_e214(lock)


def test_require_hashed_lock_rejects_an_orphan_hash_after_a_final_hash(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    final_hash = "    --hash=sha256:" + HASH
    marker = "pypdf==1.0" + CONTINUATION + final_hash
    lock.write_text(_valid_lock().replace(marker, marker + "\n" + final_hash), encoding="utf-8")

    _assert_e214(lock)


def test_require_hashed_lock_rejects_invalid_hash_in_the_pypdf_block(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    marker = "pypdf==1.0" + CONTINUATION
    invalid_block = marker + "    --hash=sha256:" + "z" * 64
    valid = _valid_lock()
    before, after = valid.split(marker, maxsplit=1)
    _, tail = after.split("\n", maxsplit=1)
    lock.write_text(before + invalid_block + "\n" + tail, encoding="utf-8")

    _assert_e214(lock)


def test_require_hashed_lock_normalizes_a_missing_lock_file(tmp_path: Path) -> None:
    _assert_e214(tmp_path / "missing.lock")


def test_repository_requirements_lock_is_individually_hashed() -> None:
    lock = Path(__file__).parents[2] / "requirements.lock"

    require_hashed_lock(lock)
