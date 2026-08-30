"""Turn Anthropic API `usage` into a dollar cost.

Story 3 (prompt caching) isn't implemented yet, so cache_creation/cache_read
are currently always 0 - but the math is here so it "just works" once
caching lands, instead of needing a second pass through this file.
"""

from dataclasses import dataclass

from anthropic.types import Usage

from archforge.config import MODEL_PRICING

CACHE_READ_MULTIPLIER = 0.1
# Cache writes cost 1.25x (5-minute TTL) or 2x (1-hour TTL) the input price.
# Story 3 hasn't picked a TTL yet, so this assumes the cheaper 5-minute
# default - revisit if/when a 1-hour TTL is used.
CACHE_WRITE_MULTIPLIER = 1.25


@dataclass
class CostSummary:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    cost_usd: float


def summarize_cost(
    domain_usages: list[list[Usage]], review_usage: Usage, model: str
) -> CostSummary:
    """Aggregate every API call's usage from one `generate_batch` run
    (domain agents, including any pause_turn continuations, plus the
    reviewer) into a single cost summary for the given model."""
    if model not in MODEL_PRICING:
        raise ValueError(f"no pricing configured for model {model!r}")
    pricing = MODEL_PRICING[model]

    usages = [usage for batch in domain_usages for usage in batch]
    usages.append(review_usage)

    input_tokens = sum(u.input_tokens for u in usages)
    output_tokens = sum(u.output_tokens for u in usages)
    cache_creation_input_tokens = sum(u.cache_creation_input_tokens or 0 for u in usages)
    cache_read_input_tokens = sum(u.cache_read_input_tokens or 0 for u in usages)

    cost_usd = (
        input_tokens * pricing["input"]
        + output_tokens * pricing["output"]
        + cache_read_input_tokens * pricing["input"] * CACHE_READ_MULTIPLIER
        + cache_creation_input_tokens * pricing["input"] * CACHE_WRITE_MULTIPLIER
    ) / 1_000_000

    return CostSummary(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cost_usd=cost_usd,
    )
