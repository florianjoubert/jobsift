"""Normalised job schema shared by all connectors."""

from enum import StrEnum

from pydantic import BaseModel


class JobSource(StrEnum):
    arbeitnow = "arbeitnow"
    wttj = "wttj"
    france_travail = "france_travail"
    adzuna = "adzuna"
    private = "private"  # private/local connector (not version-controlled)


class Job(BaseModel):
    job_id: str
    source: JobSource
    title: str
    company: str = ""
    location: str = ""
    country: str = ""          # normalised country name if determinable, otherwise ""
    url: str = ""
    description: str = ""
    posted_at: str = ""
    salary: str | None = None
    remote: bool = False
    contract_type: str | None = None


class ScoredJob(Job):
    relevance_score: int = 0
    ai_summary: str = ""
    ai_pros: list[str] = []
    ai_cons: list[str] = []
