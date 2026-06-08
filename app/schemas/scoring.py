"""Structured output schema for scoring."""

from pydantic import BaseModel


class ScoreItem(BaseModel):
    job_id: str
    score: int
    summary: str
    pros: list[str] = []
    cons: list[str] = []


class ScoreBatch(BaseModel):
    items: list[ScoreItem]
