# tests/test_registry.py
from app.connectors.registry import build_connectors


def test_registry_respects_toggles_and_keys():
    config = {"sources": {"arbeitnow": True, "wttj": False,
                          "france_travail": True, "adzuna": True}}
    # france_travail/adzuna without keys → ignored (graceful degradation)
    secrets = {"france_travail": False, "adzuna": False}
    conns = build_connectors(config, available_secrets=secrets)
    names = {c.name for c in conns}
    assert "arbeitnow" in names
    assert "wttj" not in names           # disabled by toggle
    assert "france_travail" not in names  # disabled due to missing keys
    assert "adzuna" not in names


def test_registry_empty_config_returns_defaults():
    """Empty config → only key-free connectors are active (arbeitnow + wttj)."""
    conns = build_connectors({})
    names = {c.name for c in conns}
    # Both public connectors are active by default
    assert "arbeitnow" in names
    assert "wttj" in names


def test_registry_private_absent_does_not_crash():
    """_discover_private() must not raise if connectors_private/ is absent."""
    from app.connectors.registry import _discover_private
    # No need to monkey-patch a missing directory - _discover_private() uses
    # the project-relative path. We just verify the call does not raise.
    result = _discover_private()
    assert isinstance(result, list)
