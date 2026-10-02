from dataclasses import replace
from pathlib import Path

import pytest

from dwg_to_pdf.cad.selection import CadCandidate, CadSelection, select_candidate
from dwg_to_pdf.errors import AppError


def candidate(prog_id="AutoCAD.Application.25", clsid="{A}"):
    return CadCandidate("autocad", prog_id, clsid, Path("C:/CAD/acad.exe"), "AutoCAD", "25.0")


def assert_code(code, selection, candidates):
    with pytest.raises(AppError) as error:
        select_candidate(selection, candidates)
    assert error.value.code == code


def test_zero_candidates_e220():
    assert_code("E220", CadSelection("autocad", None, True), ())


def test_one_candidate_selected():
    only = candidate()
    assert select_candidate(CadSelection("autocad", None, True), (only,)) == only


def test_multiple_candidates_require_explicit_selection():
    a, b = candidate(), candidate("AutoCAD.Application.24", "{B}")
    assert_code("E221", CadSelection("autocad", None, True), (a, b))
    assert select_candidate(CadSelection("autocad", b.prog_id, True), (a, b)) == b


def test_alias_deduplicated_by_clsid_and_executable():
    a = candidate()
    alias = replace(a, prog_id="AutoCAD.Application")
    chosen = select_candidate(CadSelection("autocad", None, True), (alias, a))
    assert chosen == a
    assert select_candidate(CadSelection("autocad", alias.prog_id, True), (a, alias)) == alias


def test_autocad_requires_opt_in_e222():
    assert_code("E222", CadSelection("autocad", None, False), (candidate(),))


def test_does_not_fallback_to_another_provider():
    assert_code("E220", CadSelection("gstarcad", None, False), (candidate(),))


def test_missing_explicit_progid_e202():
    assert_code("E202", CadSelection("autocad", "AutoCAD.Application.99", True), (candidate(),))


def test_conflicting_registration_e202():
    a = candidate()
    assert_code("E202", CadSelection("autocad", a.prog_id, True), (a, replace(a, clsid="{B}")))


@pytest.mark.parametrize("provider", ["other", "AutoCAD", "", None])
def test_unknown_provider_is_not_silently_accepted(provider):
    assert_code("E001", CadSelection(provider, None, False), ())
