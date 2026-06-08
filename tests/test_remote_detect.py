"""TDD tests for app/services/remote_detect.py."""

import pytest

from app.services.remote_detect import is_remote

# ---- True cases: EN markers ----

@pytest.mark.parametrize("text", [
    "This is a Full Remote position building LLM apps.",
    "100% remote team, distributed across Europe.",
    "Fully remote role, apply from anywhere.",
    "We are a remote-first company.",
    "Remote first culture, async communication.",
    "Work from home, flexible hours.",
    "WFH policy in place, no commute needed.",
    "Distributed team across FR and DE.",
    "Remote opportunity for senior engineers.",
    "Home office setup provided.",
])
def test_is_remote_en_markers(text):
    assert is_remote(text) is True


# ---- True cases: FR markers ----

@pytest.mark.parametrize("text", [
    "Poste en télétravail complet, full remote.",
    "Télé-travail accepté, déplacements rares.",
    "100% télétravail, équipe distribuée.",
    "Poste à distance, toute la France.",
    "Mode distanciel permanent.",
])
def test_is_remote_fr_markers(text):
    assert is_remote(text) is True


# ---- False cases: on-site listings with no remote marker ----

@pytest.mark.parametrize("text", [
    "Poste en présentiel à Paris, équipe sur site.",
    "Bureau à Lyon, présence obligatoire 5j/5.",
    "On-site position in Bordeaux, office mandatory 5 days a week.",
    "Hybrid role, 3 days in office required.",
])
def test_is_remote_onsite_false(text):
    assert is_remote(text) is False


# ---- Edge cases ----

def test_is_remote_empty():
    assert is_remote("") is False


def test_is_remote_case_insensitive():
    assert is_remote("FULL REMOTE position") is True
    assert is_remote("TÉLÉTRAVAIL COMPLET") is True


def test_is_remote_bare_remote_word():
    assert is_remote("Remote AI engineer role in Europe.") is True
