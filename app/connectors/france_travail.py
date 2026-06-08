"""France Travail connector (Job Listings API v2, OAuth2 client-credentials).

Authentication: POST client_credentials to TOKEN_URL → access_token.
Search:         GET SEARCH_URL?motsCles=<kw>&pays=01&range=0-49

Fields returned by the API (documented on francetravail.io):
  id, intitule, entreprise.nom, lieuTravail.libelle,
  description, origineOffre.urlOrigine, dateCreation, typeContrat.

All listings from this endpoint are in France (pays=01), so country is
hardcoded to "France" without geocoding.
"""

import logging

import requests

from app.connectors.base import SearchCriteria
from app.schemas.job import Job, JobSource

logger = logging.getLogger(__name__)

TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=%2Fpartenaire"
)
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"


class FranceTravailConnector:
    name = "france_travail"

    def _token(self) -> str:
        """Obtain an OAuth2 client-credentials token. Reads secrets from settings."""
        # Late import: settings are only read at call time, never at import time.
        from app.config import settings

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.france_travail_client_id,
                "client_secret": settings.france_travail_client_secret,
                "scope": SCOPE,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def fetch(self, criteria: SearchCriteria) -> list[Job]:
        """Fetch listings for each keyword and normalise them into Job objects.

        Returns [] on authentication failure or network error (never raises).
        """
        try:
            token = self._token()
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.warning(f"France Travail auth failed: {e}")
            return []

        headers = {"Authorization": f"Bearer {token}"}
        jobs: list[Job] = []

        for kw in criteria.keywords or [""]:
            try:
                resp = requests.get(
                    SEARCH_URL,
                    headers=headers,
                    params={"motsCles": kw, "pays": "01", "range": "0-49"},
                    timeout=30,
                )
                # The API returns 206 Partial Content when there are more results.
                if resp.status_code not in (200, 206):
                    logger.warning(
                        f"France Travail search '{kw}' HTTP {resp.status_code}"
                    )
                    continue
                results = resp.json().get("resultats", [])
            except (requests.RequestException, ValueError) as e:
                logger.warning(f"France Travail search '{kw}' failed: {e}")
                continue

            for r in results:
                jobs.append(
                    Job(
                        job_id=f"ft_{r.get('id', '')}",
                        source=JobSource.france_travail,
                        title=r.get("intitule", ""),
                        company=(r.get("entreprise") or {}).get("nom", ""),
                        location=(r.get("lieuTravail") or {}).get("libelle", ""),
                        # pays=01 endpoint = France only.
                        country="France",
                        url=(r.get("origineOffre") or {}).get("urlOrigine", ""),
                        description=(r.get("description") or "")[:5000],
                        posted_at=r.get("dateCreation", ""),
                        contract_type=r.get("typeContrat", "") or None,
                    )
                )

        # Deduplicate by id (multiple keywords may return the same listing).
        uniq = {j.job_id: j for j in jobs}
        logger.info(f"France Travail: {len(uniq)} offres récupérées")
        return list(uniq.values())
