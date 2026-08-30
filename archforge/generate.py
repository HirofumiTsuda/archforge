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
from anthropic.types import Usage

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


MAX_PAUSE_TURN_CONTINUATIONS = 5


async def _generate_domain_batch(
    client: anthropic.AsyncAnthropic, exam_name: str, domain: str, count: int, model: str
) -> tuple[DomainBatch, list[Usage]]:
    user_message = f"Write {count} items for this domain."
    system = get_domain_system_prompt(exam_name=exam_name, domain=domain)
    tools = [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "allowed_domains": [
                "docs.claude.com",
                "claude.com",
                "anthropic.skilljar.com",
                "anthropic-partners.skilljar.com",
            ],
            # Without a cap, search result content (billed as input tokens on
            # the next step of the same call) can dominate the cost of a
            # generate run - a real run hit 152K input tokens. 3 searches per
            # domain call is enough to verify a couple of distinct facts.
            "max_uses": 3,
        }
    ]
    output_config = {
        "format": {"type": "json_schema", "schema": DomainBatch.model_json_schema()},
        "effort": "low",
    }

    # web_search runs a server-side loop that can stop early (default limit:
    # 10 iterations) with stop_reason "pause_turn". Resume by re-sending the
    # conversation so far - the API sees the trailing server_tool_use block
    # and continues where it left off (no "Continue." message needed).
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    attempt = 0
    usage_list: list[Usage] = []
    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=messages,
            tools=tools,
            output_config=output_config,
        )
        usage_list.append(response.usage)
        if response.stop_reason != "pause_turn":
            break
        attempt += 1
        if attempt > MAX_PAUSE_TURN_CONTINUATIONS:
            raise RuntimeError(
                f"web_search for domain {domain!r} did not finish after "
                f"{MAX_PAUSE_TURN_CONTINUATIONS} pause_turn continuations"
            )
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response.content},
        ]
    text = next(b.text for b in reversed(response.content) if b.type == "text")
    return DomainBatch.model_validate_json(text), usage_list


async def _review(
    client: anthropic.AsyncAnthropic, exam_name: str, batches: list[DomainBatch], model: str
) -> tuple[ReviewedBatch, Usage]:
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
    return response.parsed_output, response.usage


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
    domain_batches: list[DomainBatch] = []
    domain_usages: list[list[Usage]] = []
    for batch in batches:
        domain_batch, usage = batch
        domain_batches.append(domain_batch)
        domain_usages.append(usage)

    reviewed, review_usage = await _review(client, exam_name, list(domain_batches), model)

    return {
        "questions": [q.model_dump() for q in reviewed.questions],
        "dropped_count": reviewed.dropped_count,
        "review_notes": reviewed.review_notes,
        "raw_count": sum(len(b.questions) for b in domain_batches),
        "domain_usages": domain_usages,
        "review_usage": review_usage,
    }
