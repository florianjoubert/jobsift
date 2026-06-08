"""Build the list of active connectors (toggles + API keys + local private connectors)."""

import importlib
import importlib.util
import logging
import pkgutil
from pathlib import Path

from app.connectors.arbeitnow import ArbeitnowConnector
from app.connectors.wttj import WttjConnector

logger = logging.getLogger(__name__)


def build_connectors(config: dict, available_secrets: dict | None = None) -> list:
    """Build the list of active connectors based on config and available secrets.

    Args:
        config: dict containing the "sources" key with per-connector enable toggles.
        available_secrets: dict indicating whether API keys are present (True/False).
            If None, the Pydantic settings are consulted for key-gated connectors.

    Returns:
        List of ready-to-use connector instances.
    """
    secrets = available_secrets or {}
    toggles = (config or {}).get("sources", {})
    connectors: list = []

    # Public connectors (no API key required)
    if toggles.get("arbeitnow", True):
        connectors.append(ArbeitnowConnector())

    if toggles.get("wttj", True):
        connectors.append(WttjConnector())

    # Key-gated connectors: France Travail
    if toggles.get("france_travail", True):
        has_ft_key = (
            secrets.get("france_travail")
            if available_secrets is not None
            else _check_settings("france_travail")
        )
        if has_ft_key:
            try:
                from app.connectors.france_travail import FranceTravailConnector
                connectors.append(FranceTravailConnector())
            except ImportError as e:
                logger.warning(f"Connecteur france_travail non disponible : {e}")

    # Key-gated connectors: Adzuna
    if toggles.get("adzuna", True):
        has_adzuna_key = (
            secrets.get("adzuna")
            if available_secrets is not None
            else _check_settings("adzuna")
        )
        if has_adzuna_key:
            try:
                from app.connectors.adzuna import AdzunaConnector
                connectors.append(AdzunaConnector())
            except ImportError as e:
                logger.warning(f"Connecteur adzuna non disponible : {e}")

    # Local private connectors (placed in connectors_private/, gitignored)
    connectors.extend(_discover_private())

    logger.info(f"Connecteurs actifs : {[c.name for c in connectors]}")
    return connectors


def _check_settings(name: str) -> bool:
    """Check whether the API keys for a connector are defined in settings."""
    try:
        from app.config import settings
        if name == "france_travail":
            return bool(settings.france_travail_client_id and settings.france_travail_client_secret)
        if name == "adzuna":
            return bool(settings.adzuna_app_id and settings.adzuna_app_key)
    except Exception:
        pass
    return False


def _discover_private() -> list:
    """Dynamically load connectors placed in connectors_private/.

    Convention: each .py file must expose a ``Connector`` class with a ``name``
    attribute and a ``fetch(criteria)`` method. Files ending with ``_example``
    or starting with ``_`` are ignored.
    Never raises: returns [] if the directory is missing or empty.
    """
    private_dir = Path(__file__).parent.parent.parent / "connectors_private"
    found: list = []
    if not private_dir.exists():
        return found

    for mod in pkgutil.iter_modules([str(private_dir)]):
        if mod.name.endswith("_example") or mod.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                mod.name, private_dir / f"{mod.name}.py"
            )
            if spec is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "Connector"):
                found.append(module.Connector())
                logger.info(f"Connecteur privé chargé : {mod.name}")
        except Exception as e:
            logger.warning(f"Connecteur privé '{mod.name}' non chargé : {e}")

    return found
