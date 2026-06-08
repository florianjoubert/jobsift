"""POST /runs - triggers a pipeline run as a background task."""

import uuid

from fastapi import APIRouter, BackgroundTasks

from app.api.runner import RUNS, execute_run
from app.schemas.run import RunSummary

router = APIRouter()


@router.post("/runs", response_model=RunSummary)
def trigger_run(background_tasks: BackgroundTasks):
    run_id = uuid.uuid4().hex[:8]
    RUNS[run_id] = RunSummary(run_id=run_id, status="running")
    background_tasks.add_task(execute_run, run_id)
    return RUNS[run_id]


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str):
    return RUNS.get(run_id, RunSummary(run_id=run_id, status="unknown"))
