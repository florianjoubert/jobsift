"""Shared run executor used by both the API and the CLI."""

import logging
from pathlib import Path

import yaml

from app.config import settings
from app.connectors.registry import build_connectors
from app.schemas.run import RunSummary
from app.services.pipeline import run as run_pipeline
from app.services.profile_loader import load_profile

logger = logging.getLogger(__name__)
RUNS: dict[str, RunSummary] = {}

# Project root: resolves correctly regardless of the working directory
# (fixes the relative-path bug reported in Phase 5).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_config() -> dict:
    """Load config.yaml from the project root (CWD-independent)."""
    config_path = _PROJECT_ROOT / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def _available_secrets() -> dict:
    """Return a mapping of connector names to whether their API keys are set."""
    return {
        "france_travail": bool(
            settings.france_travail_client_id and settings.france_travail_client_secret
        ),
        "adzuna": bool(settings.adzuna_app_id and settings.adzuna_app_key),
    }


def execute_run(run_id: str | None = None) -> RunSummary:
    """Run the full pipeline and update RUNS if a run_id is provided."""
    config = _load_config()
    profile_path = _PROJECT_ROOT / "profile.md"
    connectors = build_connectors(config, available_secrets=_available_secrets())
    counts = run_pipeline(connectors, config, profile=load_profile(profile_path))
    summary = RunSummary(run_id=run_id or "cli", status="done", **counts)
    if run_id:
        RUNS[run_id] = summary
    return summary
