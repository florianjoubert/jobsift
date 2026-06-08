"""Heuristic detection of fully remote work in a job listing.

Simple approach: substring matching on lowercased text.
Negations are NOT handled - that nuance is left to the LLM.
"""

# FR and EN markers indicating full remote / remote work.
_REMOTE_MARKERS = (
    "full remote",
    "100% remote",
    "fully remote",
    "remote-first",
    "remote first",
    "work from home",
    "wfh",
    "distributed team",
    "remote",
    "télétravail",
    "télé-travail",
    "100% télétravail",
    "à distance",
    "distanciel",
    "home office",
)


def is_remote(text: str) -> bool:
    """Return True if the text contains at least one remote-work marker.

    Case-insensitive substring matching.
    Returns False for empty text.
    """
    if not text:
        return False
    normalized = text.lower()
    return any(marker in normalized for marker in _REMOTE_MARKERS)
