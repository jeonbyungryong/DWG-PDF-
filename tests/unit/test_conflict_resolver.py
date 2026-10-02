from pathlib import Path

import pytest

from dwg_to_pdf.conflict_resolver import next_copy_name, resolve_collision
from dwg_to_pdf.errors import AppError


def test_next_copy_name_uses_korean_copy_suffix_sequence(tmp_path: Path) -> None:
    output = tmp_path / "part.pdf"
    output.write_bytes(b"old")
    first_copy = tmp_path / "part - 복사본.pdf"
    first_copy.write_bytes(b"old")

    assert next_copy_name(output) == tmp_path / "part - 복사본 2.pdf"


def test_resolve_collision_returns_requested_path_when_absent(tmp_path: Path) -> None:
    output = tmp_path / "part.pdf"

    assert resolve_collision(output, "copy") == output


@pytest.mark.parametrize("policy", ["skip", "ask"])
def test_resolve_collision_holds_existing_output_for_noninteractive_policies(
    tmp_path: Path, policy: str
) -> None:
    output = tmp_path / "part.pdf"
    output.write_bytes(b"old")

    with pytest.raises(AppError) as raised:
        resolve_collision(output, policy)  # type: ignore[arg-type]

    assert raised.value.code == "E500"


def test_resolve_collision_copy_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "part.pdf"
    output.write_bytes(b"old")

    assert resolve_collision(output, "copy") == tmp_path / "part - 복사본.pdf"
    assert output.read_bytes() == b"old"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [("OVERWRITE", "part.pdf"), (" copy ", "part - 복사본.pdf")],
)
def test_resolve_collision_ask_accepts_case_insensitive_safe_choices(
    tmp_path: Path, monkeypatch, reply: str, expected: str
) -> None:
    output = tmp_path / "part.pdf"
    output.write_bytes(b"old")
    monkeypatch.setattr("dwg_to_pdf.conflict_resolver._prompt_conflict", lambda path: reply)

    assert resolve_collision(output, "ask") == tmp_path / expected


def test_resolve_collision_ask_writes_one_prompt_to_stderr_not_stdout(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    output = tmp_path / "part.pdf"
    output.write_bytes(b"old")

    def console_input(prompt: str = "") -> str:
        print(prompt, end="")
        return "copy"

    monkeypatch.setattr("builtins.input", console_input)

    assert resolve_collision(output, "ask") == tmp_path / "part - 복사본.pdf"

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("PDF already exists") == 1


@pytest.mark.parametrize("reply", ["", "delete", EOFError(), RuntimeError("input failed")])
def test_resolve_collision_ask_fails_closed_for_invalid_or_unavailable_input(
    tmp_path: Path, monkeypatch, reply: object
) -> None:
    output = tmp_path / "part.pdf"
    output.write_bytes(b"old")

    def prompt(path: Path) -> str:
        if isinstance(reply, BaseException):
            raise reply
        return str(reply)

    monkeypatch.setattr("dwg_to_pdf.conflict_resolver._prompt_conflict", prompt)
    with pytest.raises(AppError) as raised:
        resolve_collision(output, "ask")

    assert raised.value.code == "E500"


def test_next_copy_name_fails_closed_after_bounded_attempts(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "part.pdf"
    monkeypatch.setattr("dwg_to_pdf.conflict_resolver.MAX_COPY_NAME_ATTEMPTS", 2)
    monkeypatch.setattr("dwg_to_pdf.conflict_resolver._exists", lambda path: True)

    with pytest.raises(AppError) as raised:
        next_copy_name(output)

    assert raised.value.code == "E500"
