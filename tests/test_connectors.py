"""Tests for the Arbeitnow and WTTJ connectors.

Mocking strategy: the connectors use `requests` (not httpx), so `respx`
cannot intercept them. We use `unittest.mock.patch` on `requests.get` /
`requests.post` instead.
"""

from unittest.mock import MagicMock, patch

from app.connectors.arbeitnow import ArbeitnowConnector
from app.connectors.base import SearchCriteria
from app.schemas.job import JobSource

# ---------------------------------------------------------------------------
# Arbeitnow
# ---------------------------------------------------------------------------

ARBEITNOW_SAMPLE = {
    "data": [
        {
            "slug": "ai-engineer-acme-12345",
            "company_name": "ACME",
            "title": "AI Engineer",
            "description": "<p>We build agents.</p>",
            "remote": True,
            "location": "Berlin",
            "url": "https://www.arbeitnow.com/jobs/ai-engineer-acme-12345",
            "created_at": 1717200000,
            "job_types": ["full-time"],
        }
    ],
    "links": {"next": None},
    "meta": {"current_page": 1, "last_page": 1},
}

ARBEITNOW_SAMPLE_WITH_COUNTRY = {
    "data": [
        {
            "slug": "pm-paris-67890",
            "company_name": "Startup",
            "title": "Product Manager",
            "description": "Great role.",
            "remote": False,
            "location": "Paris, Ile-de-France, France",
            "url": "https://www.arbeitnow.com/jobs/pm-paris-67890",
            "created_at": 1717200000,
            "job_types": ["full-time"],
        }
    ],
    "links": {"next": None},
    "meta": {"current_page": 1, "last_page": 1},
}


def _mock_response(payload):
    """Create a fake requests Response object."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = payload
    return mock


def test_arbeitnow_normalizes_to_job():
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == JobSource.arbeitnow
    assert j.title == "AI Engineer"
    assert j.company == "ACME"
    assert j.remote is True
    assert j.url.endswith("ai-engineer-acme-12345")
    assert "<p>" not in j.description  # HTML stripped


def test_arbeitnow_bare_city_leaves_country_empty():
    """City-only location → country stays empty (no country is invented)."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].country == ""
    assert jobs[0].location == "Berlin"


def test_arbeitnow_parses_country_from_location_with_commas():
    """Location = 'City, Region, Country' → the last segment is extracted as country."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE_WITH_COUNTRY)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].country == "France"
    assert jobs[0].remote is False


def test_arbeitnow_remote_bool_is_set():
    """The remote field from the API must be mapped to Job.remote."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].remote is True


def test_arbeitnow_returns_empty_on_request_error():
    """Network error → [] without raising an exception."""
    import requests as req

    with patch("requests.get", side_effect=req.RequestException("timeout")):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs == []


# ---------------------------------------------------------------------------
# WTTJ
# ---------------------------------------------------------------------------

from app.connectors.wttj import WttjConnector  # noqa: E402

WTTJ_SAMPLE_HIT = {
    "reference": "ref-1",
    "name": "Product Manager",
    "organization": {"name": "ACME", "slug": "acme-co"},
    "offices": [{"city": "None", "country": "United States"}],
    "slug": "pm-acme",
    "summary": "Great role",
    "published_at_date": "2026-06-06",
    "remote": "fulltime",
    "contract_type": "full_time",
}


def test_wttj_sets_country_from_offices():
    conn = WttjConnector()
    jobs = conn._normalize_hits([WTTJ_SAMPLE_HIT])  # test normalisation in isolation
    assert len(jobs) == 1
    assert jobs[0].country == "United States"  # → will be rejected by GeoFilter
    assert jobs[0].source.value == "wttj"


def test_wttj_url_uses_company_slug():
    """Regression: the URL must be /fr/companies/{org}/jobs/{slug}.
    The shortcut /jobs/{slug} returns a soft-404 (HTTP 200 but "page not found")."""
    conn = WttjConnector()
    job = conn._normalize_hits([WTTJ_SAMPLE_HIT])[0]
    assert job.url == "https://www.welcometothejungle.com/fr/companies/acme-co/jobs/pm-acme"


def test_wttj_strips_none_city():
    """city='None' must be ignored in the location field."""
    conn = WttjConnector()
    jobs = conn._normalize_hits([WTTJ_SAMPLE_HIT])
    # city was 'None' → location = country only, or 'Remote'
    assert "None" not in jobs[0].location


def test_wttj_remote_fulltime_maps_to_true():
    conn = WttjConnector()
    jobs = conn._normalize_hits([WTTJ_SAMPLE_HIT])
    assert jobs[0].remote is True


def test_wttj_fetch_mocked():
    """fetch() with a mocked HTTP POST → must return normalised Job objects."""
    algolia_response = {
        "results": [
            {
                "hits": [WTTJ_SAMPLE_HIT],
                "nbPages": 1,
            }
        ]
    }

    with patch("requests.post", return_value=_mock_response(algolia_response)):
        conn = WttjConnector()
        jobs = conn.fetch(SearchCriteria())

    assert len(jobs) == 1
    assert jobs[0].source == JobSource.wttj
    assert jobs[0].country == "United States"


def test_wttj_query_uses_country_code_facet():
    """Regression: the Algolia pre-filter must target offices.country_code (ISO codes).
    The offices.country facet (full names) returns 0 hits - verified against the real API."""
    algolia_response = {"results": [{"hits": [], "nbPages": 1}]}
    with patch("requests.post", return_value=_mock_response(algolia_response)) as mock_post:
        WttjConnector().fetch(SearchCriteria())
    params = mock_post.call_args.kwargs["json"]["requests"][0]["params"]
    assert "offices.country_code" in params
    assert '"offices.country"' not in params


def test_wttj_posted_at_prefers_iso_date_string():
    """posted_at must prefer published_at_date (ISO string) over published_at (unix timestamp)."""
    hit_with_both = {
        **WTTJ_SAMPLE_HIT,
        "published_at": 1749168000,  # unix timestamp
        "published_at_date": "2026-06-06",  # ISO string
    }
    conn = WttjConnector()
    jobs = conn._normalize_hits([hit_with_both])
    assert jobs[0].posted_at == "2026-06-06"


# ---------------------------------------------------------------------------
# Arbeitnow - Fix 1: a region/state must not be mistaken for a country
# ---------------------------------------------------------------------------

ARBEITNOW_SAMPLE_REGION = {
    "data": [
        {
            "slug": "dev-frankfurt-11111",
            "company_name": "DevCorp",
            "title": "Developer",
            "description": "A role in Frankfurt.",
            "remote": False,
            "location": "Frankfurt, Hessen",
            "url": "https://www.arbeitnow.com/jobs/dev-frankfurt-11111",
            "created_at": 1717200000,
            "job_types": ["full-time"],
        }
    ],
    "links": {"next": None},
    "meta": {"current_page": 1, "last_page": 1},
}

ARBEITNOW_SAMPLE_GERMANY = {
    "data": [
        {
            "slug": "dev-berlin-22222",
            "company_name": "DevCorp",
            "title": "Developer",
            "description": "A role in Berlin.",
            "remote": False,
            "location": "Berlin, Berlin, Germany",
            "url": "https://www.arbeitnow.com/jobs/dev-berlin-22222",
            "created_at": 1717200000,
            "job_types": ["full-time"],
        }
    ],
    "links": {"next": None},
    "meta": {"current_page": 1, "last_page": 1},
}

ARBEITNOW_SAMPLE_TX = {
    "data": [
        {
            "slug": "dev-austin-33333",
            "company_name": "DevCorp",
            "title": "Developer",
            "description": "A role in Austin.",
            "remote": False,
            "location": "Austin, TX",
            "url": "https://www.arbeitnow.com/jobs/dev-austin-33333",
            "created_at": 1717200000,
            "job_types": ["full-time"],
        }
    ],
    "links": {"next": None},
    "meta": {"current_page": 1, "last_page": 1},
}


def test_arbeitnow_region_not_treated_as_country():
    """'Frankfurt, Hessen': Hessen is a German region, not a country → country=""."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE_REGION)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].country == ""


def test_arbeitnow_state_not_treated_as_country():
    """'Austin, TX': TX is a US state, not a country → country=""."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE_TX)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].country == ""


def test_arbeitnow_parses_real_country():
    """'Berlin, Berlin, Germany' → country='Germany'; city only → country=''."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE_GERMANY)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].country == "Germany"


# ---------------------------------------------------------------------------
# Arbeitnow - Fix 2: HTML entities in the description must be decoded
# ---------------------------------------------------------------------------

ARBEITNOW_SAMPLE_HTML_ENTITIES = {
    "data": [
        {
            "slug": "dev-entity-44444",
            "company_name": "EntityCorp",
            "title": "Developer",
            "description": "<p>Travail &amp; passion &lt;important&gt;</p>",
            "remote": True,
            "location": "Paris, Ile-de-France, France",
            "url": "https://www.arbeitnow.com/jobs/dev-entity-44444",
            "created_at": 1717200000,
            "job_types": ["full-time"],
        }
    ],
    "links": {"next": None},
    "meta": {"current_page": 1, "last_page": 1},
}


def test_arbeitnow_decodes_html_entities():
    """&amp; and &lt; must be decoded to & and < in the description."""
    with patch("requests.get", return_value=_mock_response(ARBEITNOW_SAMPLE_HTML_ENTITIES)):
        conn = ArbeitnowConnector()
        jobs = conn.fetch(SearchCriteria())

    assert "&amp;" not in jobs[0].description
    assert "&lt;" not in jobs[0].description
    assert "&" in jobs[0].description
    assert "<important>" in jobs[0].description


# ---------------------------------------------------------------------------
# France Travail
# ---------------------------------------------------------------------------

from app.connectors.france_travail import FranceTravailConnector  # noqa: E402
from app.schemas.job import JobSource as _JobSource  # noqa: E402 (already imported above)

# Representative payload based on the Job Listings API v2 documentation.
FT_TOKEN_RESPONSE = {"access_token": "tok_test_123", "token_type": "Bearer", "expires_in": 1500}

FT_SEARCH_RESPONSE = {
    "resultats": [
        {
            "id": "142VXYZ",
            "intitule": "Ingénieur IA",
            "entreprise": {"nom": "TechCorp SA"},
            "lieuTravail": {"libelle": "75 - PARIS"},
            "description": "Développement de modèles ML en production.",
            "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/142VXYZ"},
            "dateCreation": "2026-06-05T08:00:00.000Z",
            "typeContrat": "CDI",
        }
    ]
}

# Dedup payload: same listing returned for two different keywords.
FT_SEARCH_RESPONSE_DEDUP = {
    "resultats": [
        {
            "id": "142VXYZ",
            "intitule": "Ingénieur IA",
            "entreprise": {"nom": "TechCorp SA"},
            "lieuTravail": {"libelle": "75 - PARIS"},
            "description": "Développement de modèles ML en production.",
            "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/142VXYZ"},
            "dateCreation": "2026-06-05T08:00:00.000Z",
            "typeContrat": "CDI",
        }
    ]
}


def _mock_post_response(payload):
    """Create a fake requests Response object for POST calls (OAuth2 token)."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = payload
    mock.status_code = 200
    return mock


def _mock_get_ft(payload, status_code=200):
    """Create a fake requests Response object for France Travail GET calls."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = payload
    mock.status_code = status_code
    return mock


def test_france_travail_normalizes_job():
    """Full normalisation: job_id prefixed with 'ft_', country='France', correct source."""
    with (
        patch("requests.post", return_value=_mock_post_response(FT_TOKEN_RESPONSE)),
        patch("requests.get", return_value=_mock_get_ft(FT_SEARCH_RESPONSE)),
    ):
        conn = FranceTravailConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["Ingénieur IA"]))

    assert len(jobs) == 1
    j = jobs[0]
    assert j.job_id == "ft_142VXYZ"
    assert j.source == _JobSource.france_travail
    assert j.title == "Ingénieur IA"
    assert j.company == "TechCorp SA"
    assert j.location == "75 - PARIS"
    assert j.country == "France"
    assert j.url == "https://candidat.francetravail.fr/offres/142VXYZ"
    assert j.posted_at == "2026-06-05T08:00:00.000Z"
    assert j.contract_type == "CDI"


def test_france_travail_auth_failure_returns_empty():
    """OAuth2 token failure → [] without raising an exception."""
    import requests as req

    with patch("requests.post", side_effect=req.RequestException("connexion refusée")):
        conn = FranceTravailConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["data"]))

    assert jobs == []


def test_france_travail_search_network_error_returns_empty():
    """Token OK but network error on search → [] without raising an exception."""
    import requests as req

    with (
        patch("requests.post", return_value=_mock_post_response(FT_TOKEN_RESPONSE)),
        patch("requests.get", side_effect=req.RequestException("timeout")),
    ):
        conn = FranceTravailConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["data"]))

    assert jobs == []


def test_france_travail_dedup_across_keywords():
    """The same listing returned by two keywords must be deduplicated."""
    with (
        patch("requests.post", return_value=_mock_post_response(FT_TOKEN_RESPONSE)),
        patch("requests.get", return_value=_mock_get_ft(FT_SEARCH_RESPONSE_DEDUP)),
    ):
        conn = FranceTravailConnector()
        # Two keywords → two GET calls, but the listing is identical (same id)
        jobs = conn.fetch(SearchCriteria(keywords=["IA", "machine learning"]))

    assert len(jobs) == 1
    assert jobs[0].job_id == "ft_142VXYZ"


def test_france_travail_non_200_skips_keyword():
    """Non-200/206 response for a keyword → skip to the next one without raising."""
    with (
        patch("requests.post", return_value=_mock_post_response(FT_TOKEN_RESPONSE)),
        patch("requests.get", return_value=_mock_get_ft({}, status_code=401)),
    ):
        conn = FranceTravailConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["test"]))

    assert jobs == []


# ---------------------------------------------------------------------------
# Adzuna
# ---------------------------------------------------------------------------

from app.connectors.adzuna import AdzunaConnector  # noqa: E402

# Representative payload based on the Adzuna API documentation.
ADZUNA_SEARCH_RESPONSE = {
    "results": [
        {
            "id": "4567890123",
            "title": "Product Manager",
            "company": {"display_name": "InnovateCo"},
            "location": {"display_name": "Paris, Île-de-France"},
            "description": "Rejoignez notre équipe produit en pleine croissance.",
            "redirect_url": "https://api.adzuna.com/v1/api/jobs/fr/4567890123",
            "created": "2026-06-04T10:30:00Z",
            "contract_type": "permanent",
        }
    ]
}

# Dedup payload: same listing for two keywords.
ADZUNA_SEARCH_RESPONSE_DEDUP = {
    "results": [
        {
            "id": "4567890123",
            "title": "Product Manager",
            "company": {"display_name": "InnovateCo"},
            "location": {"display_name": "Paris, Île-de-France"},
            "description": "Rejoignez notre équipe produit en pleine croissance.",
            "redirect_url": "https://api.adzuna.com/v1/api/jobs/fr/4567890123",
            "created": "2026-06-04T10:30:00Z",
            "contract_type": "permanent",
        }
    ]
}


def test_adzuna_normalizes_job():
    """Full normalisation: job_id prefixed with 'adzuna_', country='France', correct source."""
    with patch("requests.get", return_value=_mock_response(ADZUNA_SEARCH_RESPONSE)):
        conn = AdzunaConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["Product Manager"]))

    assert len(jobs) == 1
    j = jobs[0]
    assert j.job_id == "adzuna_4567890123"
    assert j.source == _JobSource.adzuna
    assert j.title == "Product Manager"
    assert j.company == "InnovateCo"
    assert j.location == "Paris, Île-de-France"
    assert j.country == "France"
    assert j.url == "https://api.adzuna.com/v1/api/jobs/fr/4567890123"
    assert j.posted_at == "2026-06-04T10:30:00Z"
    assert j.contract_type == "permanent"


def test_adzuna_network_error_returns_empty():
    """Network error → [] without raising an exception."""
    import requests as req

    with patch("requests.get", side_effect=req.RequestException("timeout")):
        conn = AdzunaConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["data"]))

    assert jobs == []


def test_adzuna_non_200_returns_empty():
    """Non-200 response (raise_for_status raises) → [] without raising an exception."""
    import requests as req

    mock = MagicMock()
    mock.raise_for_status.side_effect = req.HTTPError("403 Forbidden")

    with patch("requests.get", return_value=mock):
        conn = AdzunaConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["test"]))

    assert jobs == []


def test_adzuna_dedup_across_keywords():
    """The same listing returned by two keywords must be deduplicated."""
    with patch("requests.get", return_value=_mock_response(ADZUNA_SEARCH_RESPONSE_DEDUP)):
        conn = AdzunaConnector()
        jobs = conn.fetch(SearchCriteria(keywords=["PM", "product"]))

    assert len(jobs) == 1
    assert jobs[0].job_id == "adzuna_4567890123"


def test_adzuna_empty_contract_type_becomes_none():
    """Empty or missing contract_type in the API response → None in Job."""
    response_no_contract = {
        "results": [
            {
                "id": "9999",
                "title": "Dev",
                "company": {"display_name": "Corp"},
                "location": {"display_name": "Lyon"},
                "description": "Role.",
                "redirect_url": "https://adzuna.com/9999",
                "created": "2026-06-01T00:00:00Z",
                "contract_type": "",
            }
        ]
    }
    with patch("requests.get", return_value=_mock_response(response_no_contract)):
        conn = AdzunaConnector()
        jobs = conn.fetch(SearchCriteria())

    assert jobs[0].contract_type is None
