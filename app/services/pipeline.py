"""Pipeline orchestration: fetch → dedup → geo → language → score → persist → notify."""

import logging
from pathlib import Path

from app.connectors.base import SearchCriteria
from app.db.repository import Repository
from app.services.geo_filter import GeoFilter
from app.services.language_filter import is_french_or_english
from app.services.notifier import send_email
from app.services.remote_detect import is_remote
from app.services.scoring import score_jobs

logger = logging.getLogger(__name__)


def run(
    connectors: list,
    config: dict,
    profile: str,
    db_path: Path | str = "data/jobs.db",
) -> dict:
    """Run the full collection and notification pipeline.

    Pipeline:
        1. Fetch - collect from all active connectors.
        2. Dedup - remove duplicates (by job_id + already seen in DB).
        3. Geo filter - drop listings outside the geographic scope.
        4. Language filter - drop non-FR/EN listings.
        5. Score - rate relevance via LLM.
        6. Persist - save to the database.
        7. Notify - send the email for listings >= min_relevance_score.

    Args:
        connectors: list of instantiated connectors.
        config: configuration dict (keys: search, geo, scoring, notification).
        profile: candidate profile/CV content (used for scoring).
        db_path: path to the SQLite file.

    Returns:
        Dict with counters: raw, new, scored, notified.
    """
    repo = Repository(db_path)
    criteria = SearchCriteria(
        keywords=config.get("search", {}).get("keywords", []),
        lookback_days=config.get("search", {}).get("lookback_days", 1),
    )

    # 1. Fetch
    raw = []
    for conn in connectors:
        try:
            raw.extend(conn.fetch(criteria))
        except Exception as e:
            logger.warning(f"Connecteur {conn.name} a échoué : {e}")
    logger.info(f"{len(raw)} offres brutes récupérées")

    # 2. Dedup (by current job_id + listings already known in the DB)
    seen_ids: set[str] = set()
    unique = []
    for j in raw:
        if j.job_id in seen_ids or repo.exists(j.job_id):
            continue
        seen_ids.add(j.job_id)
        unique.append(j)
    logger.info(f"{len(unique)} nouvelles offres (après déduplication)")

    # 2b. Remote enrichment - improves detection for sources that lack a remote flag
    #     (France Travail, Adzuna…). Runs before the geo filter so the
    #     allow_remote_unknown fallback can benefit from it.
    for j in unique:
        if not j.remote:
            j.remote = is_remote(f"{j.title} {j.description}")

    # 3. Geo filter - fix for the US-listings bug
    geo = GeoFilter(
        allowed_countries=config.get("geo", {}).get("allowed_countries", []),
        allow_remote_unknown=config.get("geo", {}).get("allow_remote_unknown", True),
    )
    geo_ok = [j for j in unique if geo.keep(j)]
    dropped_geo = len(unique) - len(geo_ok)
    logger.info(f"{len(geo_ok)} offres après filtre géo (rejeté : {dropped_geo})")

    # 4. Language filter - FR and EN only
    lang_ok = [
        j for j in geo_ok
        if is_french_or_english(f"{j.title}\n{j.description[:1000]}")
    ]
    dropped_lang = len(geo_ok) - len(lang_ok)
    logger.info(f"{len(lang_ok)} offres après filtre de langue (rejeté : {dropped_lang})")

    # 5. Score via LLM
    scored = score_jobs(lang_ok, profile)

    # 6. Persist - save all scored listings
    for j in scored:
        repo.save(j)

    # 7. Notify - send email for listings above the minimum threshold
    min_score = config.get("scoring", {}).get("min_relevance_score", 55)
    to_notify = sorted(
        [j for j in scored if j.relevance_score >= min_score],
        key=lambda j: j.relevance_score,
        reverse=True,
    )
    send_email(to_notify, config)
    repo.mark_notified([j.job_id for j in to_notify])

    logger.info(
        f"Pipeline terminé - brut:{len(raw)} nouvelles:{len(unique)} "
        f"scorées:{len(scored)} notifiées:{len(to_notify)}"
    )

    return {
        "raw": len(raw),
        "new": len(unique),
        "scored": len(scored),
        "notified": len(to_notify),
    }
