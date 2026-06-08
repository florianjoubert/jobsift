from pydantic import BaseModel


class RunSummary(BaseModel):
    run_id: str
    status: str
    raw: int = 0
    new: int = 0
    scored: int = 0
    notified: int = 0
