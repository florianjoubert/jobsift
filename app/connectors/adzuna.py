"""Adzuna connector (official API, free tier). /fr/ endpoint - France only.

Endpoint: GET https://api.adzuna.com/v1/api/jobs/fr/search/1

Fields returned by the API (documented on api.adzuna.com):
  id, title, company.display_name, location.display_name,
  description, redirect_url, created, contract_type.

All listings from the /fr/ endpoint are located in France,
so country is hardcoded to "France" without additional geocoding.
"""

import logging

import requests

from app.connectors.base import SearchCriteria
from app.schemas.job import Job, JobSource

logger = logging.getLogger(__name__)

BASE = "https://api.adzuna.com/v1/api/jobs/fr/search"


class AdzunaConnector:
    name = "adzuna"

    def fetch(self, criteria: SearchCriteria) -> list[Job]:
        """Fetch listings for each keyword and normalise them into Job objects.

        API keys are read from settings at call time (never at import time).
        Returns [] on network error or non-200 response (never raises).
        """
        # Late import: settings are only read when the method is called.
        from app.config import settings

        jobs: list[Job] = []

        for kw in criteria.keywords or [""]:
            try:
                resp = requests.get(
                    f"{BASE}/1",
                    params={
                        "app_id": settings.adzuna_app_id,
                        "app_key": settings.adzuna_app_key,
                        "what": kw,
                        "results_per_page": 50,
                        "max_days_old": max(criteria.lookback_days, 1),
                        "content-type": "application/json",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
            except (requests.RequestException, ValueError) as e:
                # Redact the keys: requests puts app_id/app_key in the URL, which
                # ends up in str(e) - never log them in cleartext.
                msg = str(e)
                for secret in (settings.adzuna_app_key, settings.adzuna_app_id):
                    if secret:
                        msg = msg.replace(secret, "***")
                logger.warning(f"Adzuna search '{kw}' failed: {msg}")
                continue

            for r in results:
                jobs.append(
                    Job(
                        job_id=f"adzuna_{r.get('id', '')}",
                        source=JobSource.adzuna,
                        title=r.get("title", ""),
                        company=(r.get("company") or {}).get("display_name", ""),
                        location=(r.get("location") or {}).get("display_name", ""),
                        # /fr/ endpoint = France only.
                        country="France",
                        url=r.get("redirect_url", ""),
                        description=(r.get("description") or "")[:5000],
                        posted_at=r.get("created", ""),
                        contract_type=r.get("contract_type", "") or None,
                    )
                )

        # Deduplicate by id (multiple keywords may return the same listing).
        uniq = {j.job_id: j for j in jobs}
        logger.info(f"Adzuna: {len(uniq)} offres récupérées")
        return list(uniq.values())
