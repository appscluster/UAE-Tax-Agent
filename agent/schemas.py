"""Pydantic outputs for the agent nodes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClassifierOutput(BaseModel):
    item_id: str
    conclusion: str
    reasoning: str
    corporate_tax_note: str
    confidence: float = Field(ge=0, le=1)


class AuditorOutput(BaseModel):
    item_id: str
    verdict: Literal["agree", "disagree"]
    reason: str
    saw_reasoning: bool = False


class Citation(BaseModel):
    passage_id: str
    source: str
    page: str
    text: str
    historical: bool = False


class AskAnswer(BaseModel):
    abstained: bool
    to_verify: bool
    answer_en: str
    answer_ar: str
    citations: list[Citation]
    model: str = ""
    retry_reason: str = ""
