"""CLI entry point.

Only `generate` is wired up so far. `practice`/`stats` land with story 7
(practice) and story 11 (stats) — see TASKS.md.
"""

import argparse
import asyncio

from archforge.bank import Bank
from archforge.config import BANK_PATH, EXAM_NAME, MODEL
from archforge.generate import generate_batch


async def _generate(count: int, model: str) -> None:
    result = await generate_batch(count, EXAM_NAME, model=model)

    bank = Bank(bank_path=BANK_PATH)
    existing = bank.load_bank()
    updated = bank.add_questions(existing, result["questions"])
    bank.save_bank(updated)

    print(
        f"Added {len(result['questions'])} questions "
        f"(dropped {result['dropped_count']} of {result['raw_count']} raw candidates). "
        f"Bank now has {len(updated)} questions."
    )
    print(f"Review notes: {result['review_notes']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="archforge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate new practice questions.")
    generate_parser.add_argument("--count", type=int, default=15)
    generate_parser.add_argument("--model", default=MODEL)

    args = parser.parse_args()

    if args.command == "generate":
        asyncio.run(_generate(args.count, args.model))


if __name__ == "__main__":
    main()
