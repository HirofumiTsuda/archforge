import pytest

from archforge.bank import Bank


def make_bank(tmp_path) -> Bank:
    return Bank(bank_path=str(tmp_path / "bank.json"))


def make_question(domain: str = "Agentic Architecture & Orchestration") -> dict:
    return {
        "scenario": "A team is designing a multi-agent pipeline.",
        "question": "What should they do?",
        "choices": ["A", "B", "C", "D"],
        "correct_indices": [0],
        "select_count_hint": "Select one answer.",
        "difficulty": "medium",
        "grounding_notes": "Because A is correct.",
        "domain": domain,
    }


def test_load_bank_missing_file_returns_empty_list(tmp_path):
    bank = make_bank(tmp_path)
    assert bank.load_bank() == []


def test_save_and_load_roundtrip(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question()])

    bank.save_bank(questions)

    assert bank.load_bank() == questions


def test_add_questions_assigns_id_created_at_and_empty_attempts(tmp_path):
    bank = make_bank(tmp_path)
    stored = bank.add_questions([], [make_question(), make_question()])

    assert len(stored) == 2
    for q in stored:
        assert q["id"]
        assert q["created_at"]
        assert q["attempts"] == []
    # ids are unique
    assert stored[0]["id"] != stored[1]["id"]


def test_add_questions_extends_existing_bank(tmp_path):
    bank = make_bank(tmp_path)
    existing = bank.add_questions([], [make_question()])

    updated = bank.add_questions(existing, [make_question()])

    assert len(updated) == 2


def test_unattempted_returns_only_questions_without_attempts(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question(), make_question()])
    bank.record_attempt(questions, questions[0]["id"], given_indices=[0], correct=True)

    remaining = bank.unattempted(questions)

    assert len(remaining) == 1
    assert remaining[0]["id"] == questions[1]["id"]


def test_unattempted_filters_by_domain(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions(
        [],
        [
            make_question(domain="Tool Design & MCP Integration"),
            make_question(domain="Context Management & Reliability"),
        ],
    )

    remaining = bank.unattempted(questions, domain="Tool Design & MCP Integration")

    assert len(remaining) == 1
    assert remaining[0]["domain"] == "Tool Design & MCP Integration"


def test_record_attempt_appends_attempt_with_expected_fields(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question()])
    qid = questions[0]["id"]

    bank.record_attempt(questions, qid, given_indices=[0, 2], correct=False)

    attempts = questions[0]["attempts"]
    assert len(attempts) == 1
    assert attempts[0]["given_indices"] == [0, 2]
    assert attempts[0]["correct"] is False
    assert attempts[0]["ts"]


def test_record_attempt_unknown_id_raises_key_error(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question()])

    with pytest.raises(KeyError):
        bank.record_attempt(questions, "does-not-exist", given_indices=[0], correct=True)


def test_domain_stats_counts_total_attempted_and_correct_per_domain(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions(
        [],
        [
            make_question(domain="Agentic Architecture & Orchestration"),
            make_question(domain="Agentic Architecture & Orchestration"),
            make_question(domain="Tool Design & MCP Integration"),
        ],
    )
    bank.record_attempt(questions, questions[0]["id"], given_indices=[0], correct=True)
    bank.record_attempt(questions, questions[1]["id"], given_indices=[1], correct=False)
    # third question (Tool Design) stays unattempted

    stats = bank.domain_stats(questions)

    assert stats["Agentic Architecture & Orchestration"] == {
        "total": 2,
        "attempted": 2,
        "correct": 1,
    }
    assert stats["Tool Design & MCP Integration"] == {
        "total": 1,
        "attempted": 0,
        "correct": 0,
    }


def test_domain_stats_uses_most_recent_attempt(tmp_path):
    bank = make_bank(tmp_path)
    questions = bank.add_questions([], [make_question()])
    qid = questions[0]["id"]

    bank.record_attempt(questions, qid, given_indices=[0], correct=False)
    bank.record_attempt(questions, qid, given_indices=[0], correct=True)

    stats = bank.domain_stats(questions)

    assert stats["Agentic Architecture & Orchestration"]["correct"] == 1
