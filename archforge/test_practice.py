import pytest

from archforge.bank import Bank
from archforge.practice import parse_answer, run_practice


def make_bank(tmp_path) -> Bank:
    return Bank(bank_path=str(tmp_path / "bank.json"))


def make_question(
    domain: str = "Agentic Architecture & Orchestration",
    correct_indices: list[int] | None = None,
) -> dict:
    return {
        "scenario": "A team is designing a multi-agent pipeline.",
        "question": "What should they do?",
        "choices": ["A", "B", "C", "D"],
        "correct_indices": correct_indices if correct_indices is not None else [0],
        "select_count_hint": "Select one answer.",
        "difficulty": "medium",
        "grounding_notes": "Because A is correct.",
        "domain": domain,
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("A", [0]),
        ("a", [0]),
        ("A,C", [0, 2]),
        ("a, c", [0, 2]),
        (" C , A ", [0, 2]),
    ],
)
def test_parse_answer(raw, expected):
    assert parse_answer(raw) == expected


def test_run_practice_no_unattempted_questions_prints_and_returns(tmp_path, monkeypatch, capsys):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question()])
    bank.record_attempt(questions, questions[0]["id"], [0], True)
    bank.save_bank(questions)

    def fail_input(_prompt: str) -> str:
        raise AssertionError("input() should not be called when there is nothing to practice")

    monkeypatch.setattr("builtins.input", fail_input)

    run_practice(bank, domain=None, count=None)

    assert "No unattempted questions." in capsys.readouterr().out


def test_run_practice_records_correct_attempt(tmp_path, monkeypatch):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question(correct_indices=[0])])
    bank.save_bank(questions)

    monkeypatch.setattr("builtins.input", lambda _prompt: "A")

    run_practice(bank, domain=None, count=None)

    saved = bank.load_bank()
    assert len(saved[0]["attempts"]) == 1
    assert saved[0]["attempts"][0]["correct"] is True
    assert saved[0]["attempts"][0]["given_indices"] == [0]


def test_run_practice_records_incorrect_attempt(tmp_path, monkeypatch):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question(correct_indices=[0])])
    bank.save_bank(questions)

    monkeypatch.setattr("builtins.input", lambda _prompt: "B")

    run_practice(bank, domain=None, count=None)

    saved = bank.load_bank()
    assert saved[0]["attempts"][0]["correct"] is False


def test_run_practice_respects_count(tmp_path, monkeypatch):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question(), make_question(), make_question()])
    bank.save_bank(questions)

    calls = 0

    def counting_input(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        return "A"

    monkeypatch.setattr("builtins.input", counting_input)

    run_practice(bank, domain=None, count=2)

    assert calls == 2
    saved = bank.load_bank()
    assert sum(len(q["attempts"]) for q in saved) == 2


def test_run_practice_respects_domain_filter(tmp_path, monkeypatch):
    bank = make_bank(tmp_path)
    questions = bank.add_questions(
        [],
        [
            make_question(domain="Tool Design & MCP Integration"),
            make_question(domain="Context Management & Reliability"),
        ],
    )
    bank.save_bank(questions)

    monkeypatch.setattr("builtins.input", lambda _prompt: "A")

    run_practice(bank, domain="Tool Design & MCP Integration", count=None)

    saved = bank.load_bank()
    attempted = [q for q in saved if q["attempts"]]
    assert len(attempted) == 1
    assert attempted[0]["domain"] == "Tool Design & MCP Integration"


def test_run_practice_quits_on_q_without_recording_an_attempt(tmp_path, monkeypatch, capsys):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question(), make_question()])
    bank.save_bank(questions)

    monkeypatch.setattr("builtins.input", lambda _prompt: "Q")

    run_practice(bank, domain=None, count=None)

    assert "Exiting." in capsys.readouterr().out
    saved = bank.load_bank()
    assert all(len(q["attempts"]) == 0 for q in saved)


def test_run_practice_quitting_midway_keeps_prior_attempts(tmp_path, monkeypatch):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question(), make_question(), make_question()])
    bank.save_bank(questions)

    answers = iter(["A", "Q"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    run_practice(bank, domain=None, count=None)

    saved = bank.load_bank()
    assert sum(len(q["attempts"]) for q in saved) == 1
