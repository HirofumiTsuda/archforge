from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GeneratedQuestion(BaseModel):
    # extra="forbid" so model_json_schema() emits additionalProperties: false,
    # required for the raw output_config.format path (story 2's web_search
    # generation can't use client.messages.parse() alongside server tools).
    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(description="A realistic production situation, 2-5 sentences.")
    question: str = Field(
        description="The architectural decision being asked, anchored to the scenario."
    )
    choices: list[str] = Field(
        description="4-6 answer choices, plausible distractors, no letters prefixed."
    )
    correct_indices: list[int] = Field(
        description="0-based indices into `choices` that are correct."
    )
    select_count_hint: str = Field(description='e.g. "Select one answer." or "Select two answers."')
    difficulty: Literal["easy", "medium", "hard"]
    grounding_notes: str = Field(
        description="Internal notes on why the correct answer is correct and why each "
        "distractor is wrong. Not shown to the user during practice - used later to ground "
        "the on-demand explanation so it isn't re-derived (and re-hallucinated) from scratch."
    )


class DomainBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    questions: list[GeneratedQuestion]


class ReviewedQuestion(GeneratedQuestion):
    domain: str


class ReviewedBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[ReviewedQuestion]
    dropped_count: int = Field(
        description="How many raw candidates were dropped as duplicate/ambiguous/malformed."
    )
    review_notes: str = Field(
        description="One or two sentences on what was dropped or fixed and why."
    )
