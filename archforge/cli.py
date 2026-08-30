"""CLI entry point.

`generate` and `practice` are wired up. `stats` lands with story 11 — see
TASKS.md.
"""

import argparse
import asyncio

from archforge.bank import Bank
from archforge.config import BANK_PATH, EXAM_NAME, MODEL
from archforge.cost import summarize_cost
from archforge.generate import generate_batch
from archforge.practice import run_practice


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

    cost = summarize_cost(result["domain_usages"], result["review_usage"], model)
    print(f"Cost: ${cost.cost_usd:.4f}")
    print(f"  input:          {cost.input_tokens:>8,} tokens")
    print(f"  output:         {cost.output_tokens:>8,} tokens")
    print(f"  cache_read:     {cost.cache_read_input_tokens:>8,} tokens")
    print(f"  cache_creation: {cost.cache_creation_input_tokens:>8,} tokens")


def main() -> None:
    parser = argparse.ArgumentParser(prog="archforge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate new practice questions.")
    generate_parser.add_argument("--count", type=int, default=15)
    generate_parser.add_argument("--model", default=MODEL)

    practice_parser = subparsers.add_parser("practice", help="Practice unattempted questions.")
    practice_parser.add_argument("--domain", default=None, help="Restrict to one exam domain.")
    practice_parser.add_argument(
        "--count", type=int, default=None, help="How many questions to answer (default: all)."
    )

    args = parser.parse_args()

    if args.command == "generate":
        asyncio.run(_generate(args.count, args.model))
    elif args.command == "practice":
        bank = Bank(bank_path=BANK_PATH)
        run_practice(bank, args.domain, args.count)


if __name__ == "__main__":
    main()
