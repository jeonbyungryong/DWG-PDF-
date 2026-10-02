from __future__ import annotations

import json
from pathlib import Path

import pytest

from dwg_to_pdf.calibration import choose_parameters
from dwg_to_pdf.errors import AppError
import tools.calibrate_matcher as calibration_tool


def test_choose_parameters_prefers_zero_false_approval_over_more_correct_unsafe_candidate() -> None:
    assert choose_parameters(
        [
            {"threshold": 0.6, "gap": 0.1, "false_approvals": 2, "correct_approvals": 99},
            {"threshold": 0.5, "gap": 0.2, "false_approvals": 0, "correct_approvals": 4},
        ]
    ) == {"threshold": 0.5, "gap": 0.2}


def test_choose_parameters_breaks_ties_by_gap_then_threshold() -> None:
    assert choose_parameters(
        [
            {"threshold": 0.7, "gap": 0.2, "false_approvals": 0, "correct_approvals": 5},
            {"threshold": 0.8, "gap": 0.2, "false_approvals": 0, "correct_approvals": 5},
            {"threshold": 0.9, "gap": 0.1, "false_approvals": 0, "correct_approvals": 5},
        ]
    ) == {"threshold": 0.8, "gap": 0.2}


@pytest.mark.parametrize(
    "candidates",
    [
        [],
        [{"threshold": 0.5, "gap": 0.1, "false_approvals": 1, "correct_approvals": 2}],
        [{"threshold": True, "gap": 0.1, "false_approvals": 0, "correct_approvals": 2}],
        [{"threshold": float("nan"), "gap": 0.1, "false_approvals": 0, "correct_approvals": 2}],
        [{"threshold": float("inf"), "gap": 0.1, "false_approvals": 0, "correct_approvals": 2}],
        [{"threshold": 0.5, "gap": "0.1", "false_approvals": 0, "correct_approvals": 2}],
        [{"threshold": 0.5, "gap": 0.1, "false_approvals": -1, "correct_approvals": 2}],
        [{"threshold": 0.5, "gap": 0.1, "false_approvals": 0, "correct_approvals": True}],
        [{"threshold": 0.5, "gap": 0.1, "false_approvals": 0, "correct_approvals": 2, "extra": 1}],
        [{"threshold": 0.5, "gap": 0.1, "false_approvals": 0}],
    ],
)
def test_choose_parameters_fails_closed_for_empty_unsafe_or_malformed_candidates(candidates) -> None:
    with pytest.raises(AppError) as raised:
        choose_parameters(candidates)

    assert raised.value.code == "E214"


def test_calibration_tool_atomically_publishes_selected_parameters(tmp_path: Path, capsys) -> None:
    labelled = tmp_path / "labelled.json"
    output = tmp_path / "selected.json"
    labelled.write_text(
        json.dumps([
            {"threshold": 0.4, "gap": 0.1, "false_approvals": 0, "correct_approvals": 3},
            {"threshold": 0.5, "gap": 0.2, "false_approvals": 0, "correct_approvals": 4},
        ]),
        encoding="utf-8",
    )

    assert calibration_tool.main([str(labelled), str(output)]) == 0

    assert json.loads(output.read_text(encoding="utf-8")) == {"threshold": 0.5, "gap": 0.2}
    assert capsys.readouterr().err == ""
    assert not list(tmp_path.glob(".selected.json.*.tmp"))


def test_calibration_tool_keeps_prior_output_on_invalid_input(tmp_path: Path, capsys) -> None:
    labelled = tmp_path / "invalid.json"
    output = tmp_path / "selected.json"
    labelled.write_text("not json", encoding="utf-8")
    output.write_text('{"prior": true}', encoding="utf-8")

    assert calibration_tool.main([str(labelled), str(output)]) != 0

    assert output.read_text(encoding="utf-8") == '{"prior": true}'
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_calibration_tool_keeps_prior_output_when_atomic_replace_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    labelled = tmp_path / "labelled.json"
    output = tmp_path / "selected.json"
    labelled.write_text(
        json.dumps([{"threshold": 0.5, "gap": 0.1, "false_approvals": 0, "correct_approvals": 1}]),
        encoding="utf-8",
    )
    output.write_text("prior", encoding="utf-8")

    monkeypatch.setattr(calibration_tool.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("swap failed")))

    assert calibration_tool.main([str(labelled), str(output)]) != 0

    assert output.read_text(encoding="utf-8") == "prior"
    assert len(capsys.readouterr().err.strip().splitlines()) == 1
    assert not list(tmp_path.glob(".selected.json.*.tmp"))
