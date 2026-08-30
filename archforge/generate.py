"""Multi-agent question generation.

One agent per domain runs concurrently (the "burst"), each writing
scenario-grounded items for its own domain. A single reviewer agent then
passes over the combined output to dedupe, catch ambiguous items, and check
that `correct_indices` actually matches `select_count_hint`.
"""

import asyncio
import pathlib
from typing import Any

import anthropic
import jinja2

from archforge.config import DOMAINS, MODEL
from archforge.schema import DomainBatch, ReviewedBatch


def get_domain_system_prompt(exam_name: str, domain: str) -> str:
    path = pathlib.Path(__file__).parent / "prompts" / "domain_agent_system_prompt.jinja"
    text = path.read_text()
    rendered = jinja2.Template(text).render(exam_name=exam_name, domain=domain)
    return rendered


def get_reviewer_system_prompt(exam_name: str) -> str:
    path = pathlib.Path(__file__).parent / "prompts" / "reviewer_system_prompt.jinja"
    text = path.read_text()
    rendered = jinja2.Template(text).render(exam_name=exam_name)
    return rendered


def _counts_per_domain(total: int) -> list[int]:
    raw = [total * d["weight"] for d in DOMAINS]
    counts = [max(1, round(r)) for r in raw]
    # reconcile rounding drift against the requested total
    diff = total - sum(counts)
    i = 0
    while diff != 0:
        idx = i % len(counts)
        if diff > 0:
            counts[idx] += 1
            diff -= 1
        elif counts[idx] > 1:
            counts[idx] -= 1
            diff += 1
        i += 1
    return counts


async def _generate_domain_batch(
    client: anthropic.AsyncAnthropic, exam_name: str, domain: str, count: int, model: str
) -> DomainBatch:
    response = await client.messages.create(
        model=model,
        max_tokens=16000,
        system=get_domain_system_prompt(exam_name=exam_name, domain=domain),
        messages=[{"role": "user", "content": f"Write {count} items for this domain."}],
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "allowed_domains": [
                    "docs.claude.com",
                    "claude.com",
                    "anthropic.skilljar.com",
                    "anthropic-partners.skilljar.com",
                ],
            }
        ],
        output_config={
            "format": {"type": "json_schema", "schema": DomainBatch.model_json_schema()},
            "effort": "low",
        },
    )
    text = next(b.text for b in reversed(response.content) if b.type == "text")
    return DomainBatch.model_validate_json(text)


async def _review(
    client: anthropic.AsyncAnthropic, exam_name: str, batches: list[DomainBatch], model: str
) -> ReviewedBatch:
    candidates = [
        {"domain": batch.domain, "questions": [q.model_dump() for q in batch.questions]}
        for batch in batches
    ]
    response = await client.messages.parse(
        model=model,
        max_tokens=16000,
        system=get_reviewer_system_prompt(exam_name=exam_name),
        messages=[
            {
                "role": "user",
                "content": f"Candidates grouped by domain:\n\n{candidates!r}",
            }
        ],
        output_format=ReviewedBatch,
        output_config={"effort": "low"},
    )
    return response.parsed_output


async def generate_batch(total_count: int, exam_name: str, model: str = MODEL) -> dict[str, Any]:
    """Fan out one generation agent per domain in parallel, then run one
    reviewer pass over the combined output. Returns the reviewed questions
    (as plain dicts, ready for bank.add_questions) plus review metadata."""
    client = anthropic.AsyncAnthropic()
    counts = _counts_per_domain(total_count)

    batches = await asyncio.gather(
        *[
            _generate_domain_batch(client, exam_name, d["name"], c, model)
            for d, c in zip(DOMAINS, counts, strict=True)
        ]
    )

    reviewed = await _review(client, exam_name, list(batches), model)

    return {
        "questions": [q.model_dump() for q in reviewed.questions],
        "dropped_count": reviewed.dropped_count,
        "review_notes": reviewed.review_notes,
        "raw_count": sum(len(b.questions) for b in batches),
    }
