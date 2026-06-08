"""GET /jobs - list of scored job listings."""

from fastapi import APIRouter

from app.db.repository import Repository

router = APIRouter()


@router.get("/jobs")
def list_jobs(min_score: int = 0, source: str | None = None):
    repo = Repository()
    return repo.list_jobs(min_score=min_score, source=source)
