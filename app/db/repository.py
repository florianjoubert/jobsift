"""SQLite persistence for job listings."""

import json
import sqlite3
from pathlib import Path

from app.schemas.job import ScoredJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    source TEXT,
    title TEXT,
    company TEXT,
    location TEXT,
    country TEXT,
    url TEXT,
    description TEXT,
    relevance_score INTEGER DEFAULT 0,
    ai_summary TEXT DEFAULT '',
    ai_pros TEXT DEFAULT '[]',
    ai_cons TEXT DEFAULT '[]',
    posted_at TEXT DEFAULT '',
    seen_at TEXT DEFAULT (datetime('now')),
    notified INTEGER DEFAULT 0
);
"""


class Repository:
    def __init__(self, db_path: Path | str = "data/jobs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def exists(self, job_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def save(self, job: ScoredJob) -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO jobs
               (job_id, source, title, company, location, country, url,
                description, relevance_score, ai_summary, ai_pros, ai_cons, posted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job.job_id, job.source.value, job.title, job.company, job.location,
                job.country, job.url, job.description, job.relevance_score,
                job.ai_summary, json.dumps(job.ai_pros), json.dumps(job.ai_cons),
                job.posted_at,
            ),
        )
        self.conn.commit()

    def mark_notified(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        marks = ",".join("?" for _ in job_ids)
        self.conn.execute(
            f"UPDATE jobs SET notified = 1 WHERE job_id IN ({marks})", tuple(job_ids)
        )
        self.conn.commit()

    def list_jobs(self, min_score: int = 0, source: str | None = None) -> list[dict]:
        sql = "SELECT * FROM jobs WHERE relevance_score >= ?"
        params: list = [min_score]
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY relevance_score DESC, seen_at DESC"
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]
