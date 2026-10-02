from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.domain import ScaleRatio
from dwg_to_pdf.templates.profile_store import ProfileStore, load_profile


def _fixture() -> dict[str, object]:
    return json.loads(Path("tests/fixtures/profile_1_to_50.json").read_text(encoding="utf-8"))


def _write_valid_profile(directory: Path) -> None:
    source = directory / "synthetic.dwg"
    source.write_bytes(b"synthetic reference identity")
    profile = _fixture()
    profile["source"] = {
        "path": source.name,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    (directory / "profile.json").write_text(json.dumps(profile), encoding="utf-8")


def _write_nonfinite_profile(tmp_path: Path, location: str, value: float) -> Path:
    profile = _fixture()
    if location in {"scale_anchor", "scale_value_offset", "orientation_anchor"}:
        profile[location] = [value, 0.0]
    elif location in {"frame", "reference_window"}:
        profile[location] = [[0.0, 0.0], [value, 14850.0]]
    else:
        profile[location] = value
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def test_unapproved_profile_is_rejected(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/profile_1_to_50.json").read_text(encoding="utf-8")
    (tmp_path / "profile.json").write_text(
        fixture.replace('"approved": true', '"approved": false'), encoding="utf-8"
    )
    with pytest.raises(AppError) as exc:
        ProfileStore(tmp_path, source_root=tmp_path).load_all()
    assert exc.value.code == "E308"


def test_profile_schema_rejects_unexpected_fields(tmp_path: Path) -> None:
    profile = _fixture()
    profile["invented_anchor"] = [1.0, 2.0]
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(AppError) as exc:
        load_profile(path)
    assert exc.value.code == "E308"


@pytest.mark.parametrize(
    ("location", "value"),
    [
        ("scale_anchor", float("nan")),
        ("scale_anchor", float("inf")),
        ("scale_value_offset", float("nan")),
        ("scale_value_offset", float("inf")),
        ("orientation_anchor", float("nan")),
        ("orientation_anchor", float("inf")),
        ("frame", float("nan")),
        ("frame", float("inf")),
        ("reference_window", float("nan")),
        ("reference_window", float("inf")),
        ("position_tolerance", float("nan")),
        ("position_tolerance", float("inf")),
        ("scale_value_tolerance", float("nan")),
        ("scale_value_tolerance", float("inf")),
    ],
)
def test_profile_rejects_nonfinite_geometry_and_tolerance(
    tmp_path: Path, location: str, value: float
) -> None:
    path = _write_nonfinite_profile(tmp_path, location, value)

    with pytest.raises(AppError) as exc:
        load_profile(path)
    assert exc.value.code == "E308"


def test_profile_rejects_standard_json_numeric_overflow(tmp_path: Path) -> None:
    profile = _fixture()
    profile["scale_anchor"] = [1e308, 0.0]
    encoded = json.dumps(profile).replace("1e+308", "1e309")
    path = tmp_path / "profile.json"
    path.write_text(encoded, encoding="utf-8")

    with pytest.raises(AppError) as exc:
        load_profile(path)
    assert exc.value.code == "E308"


def test_profile_store_loads_verified_source_and_finds_scale(tmp_path: Path) -> None:
    _write_valid_profile(tmp_path)
    store = ProfileStore(tmp_path, source_root=tmp_path)

    store.load_all()

    profile = store.find(ScaleRatio(Decimal("1"), Decimal("50")))
    assert profile.profile_id == "synthetic-a3-1-to-50-v1"
    assert profile.approved is True
    assert profile.scale_value_offset.x == 0.0
    assert profile.scale_value_tolerance == 5.0


@pytest.mark.parametrize("value", [0, -1, True])
def test_profile_rejects_invalid_scale_value_tolerance(tmp_path: Path, value: object) -> None:
    profile = _fixture()
    profile["scale_value_tolerance"] = value
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(AppError) as exc:
        load_profile(path)
    assert exc.value.code == "E308"


def test_profile_store_rejects_changed_source(tmp_path: Path) -> None:
    _write_valid_profile(tmp_path)
    (tmp_path / "synthetic.dwg").write_bytes(b"changed")

    with pytest.raises(AppError) as exc:
        ProfileStore(tmp_path, source_root=tmp_path).load_all()
    assert exc.value.code == "E308"


def test_profile_store_rejects_duplicate_scale_atomically(tmp_path: Path) -> None:
    _write_valid_profile(tmp_path)
    duplicate_source = tmp_path / "duplicate.dwg"
    duplicate_source.write_bytes(b"duplicate source")
    duplicate = _fixture()
    duplicate["profile_id"] = "duplicate-scale"
    duplicate["source"] = {
        "path": duplicate_source.name,
        "sha256": hashlib.sha256(duplicate_source.read_bytes()).hexdigest(),
    }
    (tmp_path / "duplicate.json").write_text(json.dumps(duplicate), encoding="utf-8")

    with pytest.raises(AppError) as exc:
        ProfileStore(tmp_path, source_root=tmp_path).load_all()
    assert exc.value.code == "E308"


def test_profile_store_rejects_out_of_universe_scale(tmp_path: Path) -> None:
    _write_valid_profile(tmp_path)
    path = tmp_path / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    profile["scale"] = {"numerator": "1", "denominator": "25"}
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(AppError) as exc:
        ProfileStore(tmp_path, source_root=tmp_path).load_all()
    assert exc.value.code == "E308"


def test_failed_reload_preserves_previously_verified_profiles(tmp_path: Path) -> None:
    _write_valid_profile(tmp_path)
    store = ProfileStore(tmp_path, source_root=tmp_path)
    scale = ScaleRatio(Decimal("1"), Decimal("50"))
    store.load_all()
    original = store.find(scale)
    (tmp_path / "synthetic.dwg").write_bytes(b"changed")

    with pytest.raises(AppError) as exc:
        store.load_all()

    assert exc.value.code == "E308"
    assert store.find(scale) == original


def test_profile_store_all_is_an_immutable_snapshot(tmp_path: Path) -> None:
    _write_valid_profile(tmp_path)
    store = ProfileStore(tmp_path, source_root=tmp_path)
    store.load_all()

    profiles = store.all()

    assert isinstance(profiles, tuple)
    assert profiles == (store.find(ScaleRatio(Decimal("1"), Decimal("50"))),)


def test_synthetic_fixture_is_not_accepted_as_an_installed_profile() -> None:
    with pytest.raises(AppError) as exc:
        ProfileStore(Path("tests/fixtures"), source_root=Path("tests/fixtures")).load_all()
    assert exc.value.code == "E308"


def test_profile_store_reports_missing_scale(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path, source_root=tmp_path)
    store.load_all()

    with pytest.raises(AppError) as exc:
        store.find(ScaleRatio(Decimal("1"), Decimal("25")))
    assert exc.value.code == "E300"


def test_profile_store_requires_explicit_source_root_and_rejects_absolute_profile_path(tmp_path: Path) -> None:
    source_root = tmp_path / "references"
    source_root.mkdir()
    source = source_root / "synthetic.dwg"
    source.write_bytes(b"portable")
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    profile = _fixture()
    profile["source"] = {"path": "synthetic.dwg", "sha256": hashlib.sha256(b"portable").hexdigest()}
    (profile_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")

    store = ProfileStore(profile_dir, source_root=source_root)
    store.load_all()
    assert store.all()[0].source_path == source.resolve()

    profile["source"]["path"] = str(source.resolve())
    (profile_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(AppError) as raised:
        ProfileStore(profile_dir, source_root=source_root).load_all()
    assert raised.value.code == "E308"
