import pytest
from anthropic.types import Usage

from archforge.cost import summarize_cost


def test_summarize_cost_aggregates_tokens_and_computes_cost():
    domain_usages = [
        [Usage(input_tokens=100, output_tokens=50)],
        [Usage(input_tokens=200, output_tokens=80)],
    ]
    review_usage = Usage(input_tokens=300, output_tokens=120)

    summary = summarize_cost(domain_usages, review_usage, "claude-sonnet-5")

    assert summary.input_tokens == 600
    assert summary.output_tokens == 250
    assert summary.cache_creation_input_tokens == 0
    assert summary.cache_read_input_tokens == 0
    # (600 * $2.00 + 250 * $10.00) / 1_000_000
    assert summary.cost_usd == pytest.approx(0.0037)


def test_summarize_cost_includes_cache_read_and_creation():
    domain_usages = [
        [
            Usage(
                input_tokens=1000,
                output_tokens=200,
                cache_read_input_tokens=500,
                cache_creation_input_tokens=1200,
            )
        ]
    ]
    review_usage = Usage(input_tokens=100, output_tokens=50)

    summary = summarize_cost(domain_usages, review_usage, "claude-sonnet-5")

    assert summary.cache_read_input_tokens == 500
    assert summary.cache_creation_input_tokens == 1200
    # (1100*$2 + 250*$10 + 500*$2*0.1 + 1200*$2*1.25) / 1_000_000
    assert summary.cost_usd == pytest.approx(0.0078)


def test_summarize_cost_sums_multiple_usages_per_domain():
    # a domain that hit pause_turn and retried has more than one Usage entry
    domain_usages = [
        [Usage(input_tokens=100, output_tokens=20), Usage(input_tokens=150, output_tokens=30)]
    ]
    review_usage = Usage(input_tokens=50, output_tokens=10)

    summary = summarize_cost(domain_usages, review_usage, "claude-sonnet-5")

    assert summary.input_tokens == 300
    assert summary.output_tokens == 60


def test_summarize_cost_unknown_model_raises():
    review_usage = Usage(input_tokens=1, output_tokens=1)

    with pytest.raises(ValueError, match="no pricing configured"):
        summarize_cost([], review_usage, "claude-made-up-model")
