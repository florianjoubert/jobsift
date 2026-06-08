"""Arbeitnow connector - public API, no key required. European + remote jobs.

Fields returned by the API (verified on a real sample 2026-06-07):
  slug, company_name, title, description, remote (bool), url, tags,
  job_types, location, created_at.

Observed `location` field formats:
  - City only            : "Hamburg", "Munich" (majority of cases)
  - "City, Region, Country": "Berlin, Berlin, Germany" (minority)
  No distinct country/country_code field exists in the API response.

Strategy:
  - If `location` has ≥ 1 comma → the last segment is treated as the country.
  - Otherwise (city only)       → country="" (the country cannot be
    determined without external geocoding, so we don't invent one).
  - remote is always mapped from the API boolean (reliable).
"""

import html
import logging
import re

import requests

from app.connectors.base import SearchCriteria
from app.schemas.job import Job, JobSource

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
_TAG_RE = re.compile(r"<[^>]+>")

# Known countries used to validate the last segment of a "City, ..., Country" location.
# Prevents a region or state (e.g. 'Hessen', 'TX') from being mistaken for a country.
_KNOWN_COUNTRIES = {
    "france", "belgium", "belgique", "luxembourg", "germany", "deutschland",
    "spain", "españa", "espagne", "italy", "italia", "italie", "netherlands",
    "nederland", "ireland", "irlande", "portugal", "austria", "österreich",
    "autriche", "poland", "polska", "pologne", "sweden", "sverige", "suède",
    "denmark", "danmark", "danemark", "finland", "suomi", "finlande",
    "united kingdom", "uk", "switzerland", "suisse", "schweiz", "norway",
    "czechia", "czech republic", "greece", "romania", "hungary",
    "united states", "usa", "canada",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags, decode HTML entities, and normalise whitespace."""
    stripped = _TAG_RE.sub(" ", text or "").strip()
    return html.unescape(stripped)


def _parse_country(location: str) -> str:
    """Extract the country from the location field when the format allows it.

    Arbeitnow may return "City, Region, Country" or "City, Country".
    The last comma-separated segment is accepted as a country only if it
    appears in _KNOWN_COUNTRIES - this avoids confusing a region (e.g.
    'Hessen') or a state (e.g. 'TX') with a country.
    Returns "" if there is no comma (city only) or if the segment is unrecognised.
    """
    if not location or "," not in location:
        # City only: the country cannot be determined without geocoding.
        return ""
    segment = location.rsplit(",", 1)[-1].strip()
    # Validate the segment against the known-countries list (case-insensitive).
    if segment.lower() in _KNOWN_COUNTRIES:
        return segment
    return ""


class ArbeitnowConnector:
    name = "arbeitnow"

    def fetch(self, criteria: SearchCriteria, max_pages: int = 3) -> list[Job]:
        """Fetch paginated listings and normalise them into Job objects."""
        jobs: list[Job] = []
        url: str | None = API_URL

        for _ in range(max_pages):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                payload = resp.json()
            except (requests.RequestException, ValueError) as e:
                logger.warning(f"Arbeitnow fetch failed: {e}")
                break

            for hit in payload.get("data", []):
                location = hit.get("location", "")
                country = _parse_country(location)

                jobs.append(
                    Job(
                        job_id=f"arbeitnow_{hit.get('slug', '')}",
                        source=JobSource.arbeitnow,
                        title=hit.get("title", ""),
                        company=hit.get("company_name", ""),
                        location=location,
                        # Country extracted from the location field when available
                        # ("City, Country" format). Empty for city-only values:
                        # no external geocoding is performed.
                        country=country,
                        url=hit.get("url", ""),
                        description=_strip_html(hit.get("description", ""))[:5000],
                        # remote mapped from the API boolean - reliable for the geo_filter.
                        remote=bool(hit.get("remote", False)),
                        contract_type=",".join(hit.get("job_types", []) or []),
                    )
                )

            next_url = (payload.get("links") or {}).get("next")
            if not next_url:
                break
            url = next_url

        logger.info(f"Arbeitnow: {len(jobs)} offres récupérées")
        return jobs
