# tests/test_pipeline.py
from app.connectors.base import SearchCriteria
from app.schemas.job import Job, JobSource, ScoredJob
from app.services import pipeline


class FakeConnector:
    name = "fake"

    def __init__(self, jobs):
        self._jobs = jobs

    def fetch(self, criteria: SearchCriteria):
        return self._jobs


def fr_job(jid):
    return Job(job_id=jid, source=JobSource.wttj, title="t", company="c",
               location="Paris, France", country="France", url="u",
               description="Une description suffisamment longue en français.")


def us_job(jid):
    return Job(job_id=jid, source=JobSource.wttj, title="t", company="c",
               location="None, United States", country="United States", url="u",
               description="A sufficiently long description in English here.")


def test_pipeline_filters_us_and_scores(monkeypatch, tmp_path):
    """The US listing must be eliminated by the geo_filter before scoring."""
    connectors = [FakeConnector([fr_job("fr1"), us_job("us1")])]

    def fake_score(jobs, profile):
        return [ScoredJob(**j.model_dump(), relevance_score=80) for j in jobs]

    sent = {}
    monkeypatch.setattr(pipeline, "score_jobs", fake_score)
    monkeypatch.setattr(pipeline, "send_email", lambda jobs, config: sent.update(n=len(jobs)))

    config = {
        "geo": {"allowed_countries": ["France"], "allow_remote_unknown": True},
        "scoring": {"min_relevance_score": 55},
        "notification": {},
    }
    result = pipeline.run(
        connectors=connectors, config=config, profile="p",
        db_path=tmp_path / "t.db",
    )
    assert result["scored"] == 1      # seul le job FR survit au geo_filter
    assert result["notified"] == 1
    assert sent["n"] == 1


def test_pipeline_dedup_skips_seen_jobs(monkeypatch, tmp_path):
    """Listings already in the database are not scored again."""
    fr = fr_job("fr_seen")
    connectors = [FakeConnector([fr])]

    scored_calls = []

    def fake_score(jobs, profile):
        scored_calls.append(jobs)
        return [ScoredJob(**j.model_dump(), relevance_score=80) for j in jobs]

    monkeypatch.setattr(pipeline, "score_jobs", fake_score)
    monkeypatch.setattr(pipeline, "send_email", lambda jobs, config: None)

    config = {
        "geo": {"allowed_countries": ["France"]},
        "scoring": {"min_relevance_score": 55},
        "notification": {},
    }
    db = tmp_path / "t.db"

    # Premier run
    r1 = pipeline.run(connectors=connectors, config=config, profile="p", db_path=db)
    assert r1["new"] == 1

    # Second run - same listing, must be deduplicated
    r2 = pipeline.run(connectors=connectors, config=config, profile="p", db_path=db)
    assert r2["new"] == 0
    assert r2["scored"] == 0


def test_pipeline_min_score_filters_notified(monkeypatch, tmp_path):
    """Only listings >= min_relevance_score are notified."""
    jobs = [fr_job("j1"), fr_job("j2")]
    connectors = [FakeConnector(jobs)]

    scores = {"j1": 80, "j2": 30}

    def fake_score(js, profile):
        return [ScoredJob(**j.model_dump(), relevance_score=scores[j.job_id]) for j in js]

    sent = {}
    monkeypatch.setattr(pipeline, "score_jobs", fake_score)
    monkeypatch.setattr(pipeline, "send_email", lambda j, c: sent.update(n=len(j)))

    config = {
        "geo": {"allowed_countries": ["France"]},
        "scoring": {"min_relevance_score": 55},
        "notification": {},
    }
    result = pipeline.run(
        connectors=connectors, config=config, profile="p",
        db_path=tmp_path / "t.db",
    )
    assert result["scored"] == 2
    assert result["notified"] == 1   # only j1 (score 80 >= 55)
    assert sent["n"] == 1
