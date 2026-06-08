"""Welcome to the Jungle connector.

Uses WTTJ's PUBLIC Algolia search endpoint - the same one their website calls,
with the public client-side search key embedded in their site. This is public,
unauthenticated data (no login, no authenticated scraping). It is not an officially
documented API, so it can be disabled at any time via `sources.wttj: false` in config.

Two key points compared to a naive implementation:
  1. The `country` field is extracted from `offices[0].country` (separate from the
     city) so that GeoFilter can reject non-EU listings by country.
  2. An Algolia `offices.country_code` filter restricts results server-side to the
     configured EU countries (reduces network traffic). GeoFilter is the safety net.
"""

import logging
import time
from datetime import date

import requests

from app.connectors.base import SearchCriteria
from app.schemas.job import Job, JobSource

logger = logging.getLogger(__name__)

ALGOLIA_URL = (
    "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries"
    "?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser"
    "&search_origin=job_search_client"
)
HEADERS = {
    "x-algolia-application-id": "CSEKHVMS53",
    # Public, search-only Algolia key (client-side, exposed on WTTJ's own website).
    "x-algolia-api-key": "4bd8f6215d0cc52b26430765769e65a0",
    "content-type": "application/json",
    "Referer": "https://www.welcometothejungle.com/",
    "Origin": "https://www.welcometothejungle.com",
}
HITS_PER_PAGE = 100

# Allowed EU countries for the Algolia server-side pre-filter (complemented by GeoFilter).
# Note: the filterable facet is `offices.country_code` (ISO codes), NOT `offices.country`
# (full country names return 0 hits - verified against the real API).
_EU_COUNTRIES_FILTER = " OR ".join(
    f'"offices.country_code":"{code}"'
    for code in (
        "FR",  # France
        "DE",  # Germany
        "ES",  # Spain
        "IE",  # Ireland
        "NL",  # Netherlands
        "BE",  # Belgium
        "PT",  # Portugal
        "IT",  # Italy
        "LU",  # Luxembourg
        "AT",  # Austria
        "PL",  # Poland
        "SE",  # Sweden
        "DK",  # Denmark
        "FI",  # Finland
    )
)


class WttjConnector:
    name = "wttj"

    def fetch(self, criteria: SearchCriteria, max_pages: int = 10) -> list[Job]:
        """Fetch WTTJ listings via Algolia and normalise them into Job objects."""
        all_hits: list[dict] = []
        page, nb_pages = 0, 1

        while page < nb_pages and page < max_pages:
            body = {
                "requests": [
                    {
                        "indexName": "wttj_jobs_production_en",
                        # Country filter added (US-bug fix): pre-filter on the Algolia side
                        # to EU countries + fulltime remote. GeoFilter remains the safety net.
                        "params": (
                            f"hitsPerPage={HITS_PER_PAGE}&page={page}&query="
                            '&filters=("contract_type":"freelance" OR "contract_type":"full_time")'
                            ' AND ("remote":"fulltime")'
                            f' AND ({_EU_COUNTRIES_FILTER})'
                            "&analytics=false"
                        ),
                    }
                ]
            }

            try:
                resp = requests.post(ALGOLIA_URL, json=body, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                result = resp.json()["results"][0]
            except (requests.RequestException, KeyError, ValueError) as e:
                logger.warning(f"WTTJ fetch failed on page {page}: {e}")
                break

            all_hits.extend(result.get("hits", []))
            nb_pages = result.get("nbPages", 1)
            page += 1

            if page < nb_pages:
                time.sleep(0.5)

        jobs = self._normalize_hits(all_hits)
        logger.info(f"WTTJ: {len(jobs)} offres normalisées")
        return jobs

    def _normalize_hits(self, hits: list[dict]) -> list[Job]:
        """Normalise a list of Algolia hits into Job objects.

        City/country split: `offices[0].country` → Job.country,
        `offices[0].city` → component of Job.location.
        This lets GeoFilter reject US listings by country, fixing the
        'None, United States' bug from the old bot.
        """
        cutoff = date.fromordinal(date.today().toordinal() - 14)
        jobs: list[Job] = []

        for hit in hits:
            published = hit.get("published_at_date", "")
            try:
                if published and date.fromisoformat(published) < cutoff:
                    continue
            except ValueError:
                pass

            offices = hit.get("offices") or [{}]
            office = offices[0] if offices else {}

            city = office.get("city") or ""
            country = office.get("country") or ""

            # city == "None" is a spurious value returned by the WTTJ API
            if city.lower() == "none":
                city = ""

            location = ", ".join(p for p in (city, country) if p) or "Remote"

            org = hit.get("organization") or {}
            org_slug = org.get("slug") or ""
            slug = hit.get("slug", "")
            # The canonical WTTJ URL requires the company slug:
            # /fr/companies/{org}/jobs/{slug}. The shortcut /jobs/{slug} returns
            # HTTP 200 but a "404 / not found" page (client-side soft-404).
            url = (
                f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{slug}"
                if org_slug
                else f"https://www.welcometothejungle.com/fr/jobs/{slug}"
            )

            jobs.append(
                Job(
                    job_id=f"wttj_{hit.get('reference', '')}",
                    source=JobSource.wttj,
                    title=hit.get("name", ""),
                    company=org.get("name", ""),
                    location=location,
                    # country extracted from offices[0].country - separated from the city
                    # so that GeoFilter can filter by country reliably.
                    country=country,
                    url=url,
                    description=(hit.get("summary") or "")[:5000],
                    # Prefer published_at_date (ISO string "YYYY-MM-DD") over published_at
                    # (unix timestamp integer) for consistency and readability of posted_at.
                    posted_at=published or str(hit.get("published_at", "") or ""),
                    remote=hit.get("remote") == "fulltime",
                    contract_type=hit.get("contract_type", ""),
                )
            )

        return jobs
