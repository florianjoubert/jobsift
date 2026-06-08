"""Geographic filter: keep France and other allowed EU countries.

This is the guard that was missing and allowed US listings to slip through.
Applied uniformly to all sources at the end of the pipeline.
"""

import logging
import re

from app.schemas.job import Job

logger = logging.getLogger(__name__)

# Markers that are explicitly out of scope, detected in country OR location.
# US cities are included to catch remote listings that have no country field.
#
# KNOWN RESIDUAL LIMITATION: a remote listing with country="" and a US city
# absent from this list will pass when allow_remote_unknown=True. This is a
# deliberate precision/recall trade-off. A future improvement would replace this
# deny-list with a positive allow-list (city → country).
_NON_EU_MARKERS = (
    "united states", "usa", "u.s.", "us timezone", "états-unis", "etats-unis",
    "canada", "brazil", "brésil", "mexico", "argentina",
    "india", "china", "singapore", "japan", "australia", "new zealand",
    "united arab emirates", "uae", "israel",
    "new york", "san francisco", "chicago", "boston", "seattle",
    "los angeles", "austin", "toronto", "vancouver",
    "denver", "miami", "dallas", "atlanta", "houston", "phoenix",
    "san diego", "philadelphia",
)

# Whole-word pattern: (?<!\w)(marker)(?!\w), markers are regex-escaped.
# Lookarounds prevent substring collisions (e.g. 'usa' inside 'Lausanne').
_MARKER_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(m) for m in _NON_EU_MARKERS) + r")(?!\w)"
)


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _has_non_eu_marker(blob: str) -> bool:
    return _MARKER_RE.search(blob) is not None


class GeoFilter:
    def __init__(self, allowed_countries: list[str], allow_remote_unknown: bool = True):
        self.allowed = {_norm(c) for c in allowed_countries}
        self.allow_remote_unknown = allow_remote_unknown

    def keep(self, job: Job) -> bool:
        country = _norm(job.country)
        location = _norm(job.location)
        blob = f"{country} {location}"

        # 1. Explicitly allowed country → authoritative (even if an ambiguous
        #    word appears elsewhere in the location).
        if country and country in self.allowed:
            return True

        # 2. Non-EU marker (country or US city), matched as a whole word to
        #    avoid substring collisions (e.g. 'usa' inside 'Lausanne').
        if _has_non_eu_marker(blob):
            return False

        # 3. Allowed country detected inside the location string (e.g. 'Dublin, Ireland').
        if any(c in location for c in self.allowed):
            return True

        # 4. Known but non-allowed country → reject.
        if country and country not in self.allowed:
            return False

        # 5. Unknown country: keep remote listings if configured to do so.
        if self.allow_remote_unknown and job.remote:
            return True

        return False
