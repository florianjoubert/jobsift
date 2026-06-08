"""Language filter: keep French or English listings only.

Inclusion bias: keeps the job on detection failure, low confidence,
or very short text.
"""

import logging

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0
logger = logging.getLogger(__name__)

ALLOWED = {"fr", "en"}
MIN_CONFIDENCE = 0.7
MIN_LENGTH = 20


def is_french_or_english(text: str) -> bool:
    if not text or len(text.strip()) < MIN_LENGTH:
        return True
    try:
        langs = detect_langs(text)
    except LangDetectException:
        return True
    if not langs:
        return True
    top = langs[0]
    if top.prob < MIN_CONFIDENCE:
        return True
    return top.lang in ALLOWED
