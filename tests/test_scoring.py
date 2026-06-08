from app.schemas.job import Job, JobSource
from app.schemas.scoring import ScoreBatch, ScoreItem
from app.services import scoring


def make_job(jid):
    return Job(job_id=jid, source=JobSource.wttj, title="AI Eng", company="ACME",
               location="Paris, France", country="France", url="u", description="desc")


def test_score_jobs_merges_scores(monkeypatch):
    def fake_call(client, jobs, profile, model):
        return ScoreBatch(items=[
            ScoreItem(job_id=j.job_id, score=70, summary="ok", pros=["a"], cons=["b"])
            for j in jobs
        ])

    monkeypatch.setattr(scoring, "_call_llm", fake_call)
    monkeypatch.setattr(scoring, "_get_client", lambda: object())

    jobs = [make_job("1"), make_job("2")]
    scored = scoring.score_jobs(jobs, profile="profil test")
    assert len(scored) == 2
    assert scored[0].relevance_score == 70
    assert scored[0].ai_pros == ["a"]


def test_score_jobs_fallback_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(scoring, "_call_llm", boom)
    monkeypatch.setattr(scoring, "_get_client", lambda: object())

    scored = scoring.score_jobs([make_job("1")], profile="p")
    assert scored[0].relevance_score == 50  # neutral fallback score


def test_norm_id_strips_job_prefix():
    assert scoring._norm_id("JOB abc") == "abc"
    assert scoring._norm_id(" job xyz ") == "xyz"
    assert scoring._norm_id("wttj_ref-1") == "wttj_ref-1"


def test_score_jobs_handles_job_prefixed_ids(monkeypatch):
    """Regression: the LLM sometimes prefixes ids with 'JOB ' → the merge must
    still be correct (otherwise everything falls back to the neutral score 50)."""
    def fake_call(client, jobs, profile, model):
        return ScoreBatch(items=[
            ScoreItem(job_id=f"JOB {j.job_id}", score=77, summary="ok") for j in jobs
        ])

    monkeypatch.setattr(scoring, "_call_llm", fake_call)
    monkeypatch.setattr(scoring, "_get_client", lambda: object())

    scored = scoring.score_jobs([make_job("1"), make_job("2")], profile="p")
    assert all(s.relevance_score == 77 for s in scored)  # no fallback to 50
