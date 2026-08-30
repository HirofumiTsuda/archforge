"""Local JSON question bank. Generation (expensive, multi-agent) and practice
(cheap, no API calls for grading) are decoupled through this file."""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

Question = dict[str, Any]


class Bank:
    def __init__(self, bank_path: str) -> None:
        self.bank_path = bank_path

    def load_bank(self) -> list[Question]:
        if not os.path.exists(self.bank_path):
            return []
        with open(self.bank_path, encoding="utf-8") as f:
            return json.load(f)

    def save_bank(self, bank: list[Question]) -> None:
        os.makedirs(os.path.dirname(self.bank_path), exist_ok=True)
        with open(self.bank_path, "w", encoding="utf-8") as f:
            json.dump(bank, f, ensure_ascii=False, indent=2)

    def add_questions(self, bank: list[Question], questions: list[Question]) -> list[Question]:
        now = datetime.now(timezone.utc).isoformat()
        for q in questions:
            q["id"] = uuid.uuid4().hex[:12]
            q["created_at"] = now
            q["attempts"] = []
        bank.extend(questions)
        return bank

    def unattempted(self, bank: list[Question], domain: str | None = None) -> list[Question]:
        return [q for q in bank if not q["attempts"] and (domain is None or q["domain"] == domain)]

    def record_attempt(
        self, bank: list[Question], qid: str, given_indices: list[int], correct: bool
    ) -> None:
        for q in bank:
            if q["id"] == qid:
                q["attempts"].append(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "given_indices": given_indices,
                        "correct": correct,
                    }
                )
                return
        raise KeyError(f"question id not found in bank: {qid}")

    def domain_stats(self, bank: list[Question]) -> dict[str, dict[str, int]]:
        stats: dict[str, dict[str, int]] = {}
        for q in bank:
            d = stats.setdefault(q["domain"], {"total": 0, "attempted": 0, "correct": 0})
            d["total"] += 1
            if q["attempts"]:
                d["attempted"] += 1
                if q["attempts"][-1]["correct"]:
                    d["correct"] += 1
        return stats
