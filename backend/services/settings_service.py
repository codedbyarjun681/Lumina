from __future__ import annotations

from sqlalchemy.orm import Session

from db import crud
from services.provider_service import list_providers

LEGACY_OPENROUTER_KEY = "openrouter_api_key"


def _setting_name(provider: str) -> str:
    return f"api_key:{provider}"


def get_api_key(db: Session, provider: str) -> str | None:
    key = crud.get_setting(db, _setting_name(provider))
    if key:
        return key
    # Backward compatibility with the original single-provider setting
    if provider == "openrouter":
        return crud.get_setting(db, LEGACY_OPENROUTER_KEY)
    return None


def set_api_key(db: Session, provider: str, api_key: str) -> None:
    crud.set_setting(db, _setting_name(provider), api_key.strip())


def api_key_is_set(db: Session, provider: str) -> bool:
    return bool(get_api_key(db, provider))


def providers_key_status(db: Session) -> dict[str, bool]:
    """Which providers currently have a key configured."""
    return {
        p["id"]: api_key_is_set(db, p["id"])
        for p in list_providers(db)
        if p["needs_api_key"]
    }


# ——— App preferences (theme, defaults) ———

PREF_KEYS = ("theme", "colorway", "default_provider", "default_model")


def get_preferences(db: Session) -> dict[str, str | None]:
    return {key: crud.get_setting(db, f"pref:{key}") for key in PREF_KEYS}


def set_preferences(db: Session, prefs: dict[str, str]) -> None:
    for key, value in prefs.items():
        if key in PREF_KEYS and value is not None:
            crud.set_setting(db, f"pref:{key}", value)


# ——— LLM selection chain ———


def resolve_llm(
    db: Session,
    conversation_provider: str | None,
    conversation_model: str | None,
    workspace_provider: str,
    workspace_model: str,
) -> tuple[str, str]:
    """Resolution order: conversation override → global default → workspace legacy."""
    prefs = get_preferences(db)
    provider = (
        conversation_provider
        or prefs["default_provider"]
        or workspace_provider
    )
    model = (
        conversation_model
        or prefs["default_model"]
        or workspace_model
    )
    return provider, model
