# tests/test_geo_filter.py
from app.schemas.job import Job, JobSource
from app.services.geo_filter import GeoFilter

ALLOWED = ["France", "Germany", "Spain", "Ireland"]


def job(country="", location="", remote=False):
    return Job(job_id="x", source=JobSource.wttj, title="t",
               country=country, location=location, remote=remote, url="u")


def test_us_job_is_rejected():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    # the exact case that was broken: WTTJ "None, United States"
    assert gf.keep(job(country="United States", location="None, United States")) is False


def test_france_job_is_kept():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="France", location="Paris, France")) is True


def test_eu_job_is_kept():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="Ireland", location="Dublin, Ireland")) is True


def test_unknown_remote_is_kept_when_allowed():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="", location="Remote", remote=True)) is True


def test_unknown_with_us_marker_in_text_is_rejected():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="", location="Remote (US timezone)", remote=True)) is False


def test_unknown_remote_rejected_when_not_allowed():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=False)
    assert gf.keep(job(country="", location="Remote", remote=True)) is False


def test_country_field_beats_ambiguous_location():
    # country=France is authoritative even if 'USA' appears in the location
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="France", location="USA Innovation Lab, Paris")) is True


def test_us_city_remote_is_rejected():
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="", location="New York", remote=True)) is False
    assert gf.keep(job(country="", location="San Francisco", remote=True)) is False


def test_usa_does_not_match_lausanne_substring():
    # 'usa' must not match inside 'Lausanne'; a Lausanne (non-EU) remote listing
    # is kept by the remote fallback, NOT wrongly rejected by the marker.
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="", location="Lausanne", remote=True)) is True


def test_us_city_denver_remote_is_rejected():
    # Regression: US cities added to _NON_EU_MARKERS must be rejected.
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="", location="Denver, CO", remote=True)) is False
    assert gf.keep(job(country="", location="Miami", remote=True)) is False


def test_eu_remote_empty_country_still_kept():
    # A remote EU listing with no country set must still pass through.
    gf = GeoFilter(allowed_countries=ALLOWED, allow_remote_unknown=True)
    assert gf.keep(job(country="", location="Remote", remote=True)) is True
