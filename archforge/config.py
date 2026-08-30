"""App config: exam metadata plus the model archforge talks to.

Domain weights are the published exam blueprint. Used to size how many
practice questions to generate per domain, and to compare against the
user's own accuracy in `stats`.
"""

EXAM_NAME = "Claude Certified Architect – Foundations (CCA-F)"

MODEL = "claude-sonnet-5"

# $ per 1M tokens, keyed by model id. Every model archforge can be pointed
# at (MODEL above, or --model once story 10 lands) needs an entry here -
# cost.py looks it up by the same string.
MODEL_PRICING = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
}

DOMAINS = [
    {"name": "Agentic Architecture & Orchestration", "weight": 0.27},
    {"name": "Tool Design & MCP Integration", "weight": 0.18},
    {"name": "Claude Code Configuration & Workflows", "weight": 0.20},
    {"name": "Prompt Engineering & Structured Output", "weight": 0.20},
    {"name": "Context Management & Reliability", "weight": 0.15},
]

BANK_PATH = "data/bank.json"
