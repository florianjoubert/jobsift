from app.db.repository import Repository
from app.schemas.job import JobSource, ScoredJob


def make_job(jid="1", score=60, source=JobSource.wttj):
    return ScoredJob(
        job_id=jid, source=source, title="t", company="c",
        location="Paris, France", country="France", url="u", description="d",
        relevance_score=score,
    )


def test_save_and_exists(tmp_path):
    repo = Repository(tmp_path / "test.db")
    assert repo.exists("1") is False
    repo.save(make_job("1"))
    assert repo.exists("1") is True


def test_list_filters_by_min_score(tmp_path):
    repo = Repository(tmp_path / "test.db")
    repo.save(make_job("low", 30))
    repo.save(make_job("high", 80))
    rows = repo.list_jobs(min_score=55)
    ids = {r["job_id"] for r in rows}
    assert ids == {"high"}


def test_mark_notified(tmp_path):
    """mark_notified must set the notified column to 1."""
    repo = Repository(tmp_path / "test.db")
    repo.save(make_job("j1"))
    # Before notification: notified = 0
    rows = repo.list_jobs()
    assert rows[0]["notified"] == 0
    repo.mark_notified(["j1"])
    rows = repo.list_jobs()
    assert rows[0]["notified"] == 1


def test_list_filters_by_source(tmp_path):
    """list_jobs(source=...) must return only listings from that source."""
    repo = Repository(tmp_path / "test.db")
    repo.save(make_job("a1", source=JobSource.arbeitnow))
    repo.save(make_job("w1", source=JobSource.wttj))
    repo.save(make_job("w2", source=JobSource.wttj))

    arbeitnow_rows = repo.list_jobs(source="arbeitnow")
    assert len(arbeitnow_rows) == 1
    assert arbeitnow_rows[0]["job_id"] == "a1"

    wttj_rows = repo.list_jobs(source="wttj")
    assert len(wttj_rows) == 2
    assert {r["job_id"] for r in wttj_rows} == {"w1", "w2"}
