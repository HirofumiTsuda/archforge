"""Exam metadata for Claude Certified Architect - Foundations (CCA-F).

Domain weights are the published exam blueprint. Used to size how many
practice questions to generate per domain, and to compare against the
user's own accuracy in `stats`.
"""

EXAM_NAME = "Claude Certified Architect – Foundations (CCA-F)"

MODEL = "claude-sonnet-5"

DOMAINS = [
    {"name": "Agentic Architecture & Orchestration", "weight": 0.27},
    {"name": "Tool Design & MCP Integration", "weight": 0.18},
    {"name": "Claude Code Configuration & Workflows", "weight": 0.20},
    {"name": "Prompt Engineering & Structured Output", "weight": 0.20},
    {"name": "Context Management & Reliability", "weight": 0.15},
]

BANK_PATH = "data/bank.json"
