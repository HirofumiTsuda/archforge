"""Interactive practice loop.

Grading is local (no API call): the correct answer already lives in
`bank.json` from generation, so `practice` and `generate` are fully
decoupled sessions. On-demand explanations (story 8) hook in after grading.
"""

import random

from archforge.bank import Bank, Question


def parse_answer(raw: str) -> list[int]:
    """Turn "A" or "A, C" into 0-based indices: [0] or [0, 2]."""
    letters = [part.strip().upper() for part in raw.split(",") if part.strip()]
    return sorted(ord(letter) - ord("A") for letter in letters)


def _display_question(question: Question) -> None:
    print()
    print(question["scenario"])
    print()
    print(f"{question['question']} ({question['select_count_hint']})")
    for i, choice in enumerate(question["choices"]):
        print(f"  {chr(ord('A') + i)}. {choice}")


def run_practice(bank: Bank, domain: str | None, count: int | None) -> None:
    """Shuffle unattempted questions (optionally filtered by domain, capped
    at `count`), and for each: show it, take an answer, grade it, and
    record the attempt - saving after every question so a session
    interrupted partway through doesn't lose what was already answered."""
    questions = bank.load_bank()
    unattempted = bank.unattempted(questions, domain=domain)

    if not unattempted:
        print("No unattempted questions.")
        return

    random.shuffle(unattempted)
    if count is not None:
        unattempted = unattempted[:count]

    for question in unattempted:
        _display_question(question)
        raw = input("Your answer (Q to quit): ")
        if raw.strip().upper() == "Q":
            print("Exiting.")
            break

        given_indices = parse_answer(raw)
        correct = given_indices == sorted(question["correct_indices"])

        print("Correct!" if correct else "Incorrect.")

        bank.record_attempt(questions, question["id"], given_indices, correct)
        bank.save_bank(questions)
