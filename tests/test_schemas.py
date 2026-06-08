from app.schemas.job import Job, JobSource, ScoredJob


def test_job_minimal_construction():
    job = Job(
        job_id="abc",
        source=JobSource.arbeitnow,
        title="AI Engineer",
        company="ACME",
        location="Paris, France",
        country="France",
        url="https://x/1",
        description="desc",
    )
    assert job.job_id == "abc"
    assert job.source == JobSource.arbeitnow
    assert job.salary is None  # optional default


def test_scored_job_extends_job():
    scored = ScoredJob(
        job_id="abc", source=JobSource.wttj, title="t", company="c",
        location="l", country="France", url="u", description="d",
        relevance_score=72, ai_summary="ok", ai_pros=["a"], ai_cons=["b"],
    )
    assert scored.relevance_score == 72
    assert scored.ai_pros == ["a"]
