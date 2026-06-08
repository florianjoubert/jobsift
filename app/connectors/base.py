"""Common interface for job-source connectors."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.schemas.job import Job


class SearchCriteria(BaseModel):
    keywords: list[str] = []
    lookback_days: int = 1


@runtime_checkable
class JobConnector(Protocol):
    name: str

    def fetch(self, criteria: SearchCriteria) -> list[Job]:
        """Fetch and normalise listings from the source. Never raises: logs and returns []."""
        ...
