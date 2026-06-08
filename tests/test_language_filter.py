# tests/test_language_filter.py
from app.services.language_filter import is_french_or_english


def test_keeps_french():
    assert is_french_or_english("Nous recherchons un ingénieur logiciel expérimenté.") is True


def test_keeps_english():
    assert is_french_or_english("We are looking for an experienced software engineer.") is True


def test_rejects_german():
    text = "Wir suchen einen erfahrenen Softwareentwickler für unser Team."
    assert is_french_or_english(text) is False


def test_keeps_short_text_inclusive():
    assert is_french_or_english("AI") is True
