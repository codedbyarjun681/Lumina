from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from services.provider_service import get_provider

OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

_MODELS_CACHE_TTL_SECONDS = 600
_models_cache: dict[str, dict] = {}


def _cached(provider: str) -> list[dict] | None:
    entry = _models_cache.get(provider)
    if entry and time.time() - entry["fetched_at"] < _MODELS_CACHE_TTL_SECONDS:
        return entry["models"]
    return None


def _store(provider: str, models: list[dict]) -> list[dict]:
    _models_cache[provider] = {"fetched_at": time.time(), "models": models}
    return models


def _fetch_json(url: str, api_key: str | None, timeout: int) -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_free_openrouter_model(model: dict) -> bool:
    pricing = model.get("pricing", {})
    try:
        prompt_price = float(pricing.get("prompt", "1"))
        completion_price = float(pricing.get("completion", "1"))
    except (TypeError, ValueError):
        return False
    return prompt_price == 0 and completion_price == 0


def _ollama_models() -> list[dict]:
    try:
        data = _fetch_json(OLLAMA_TAGS_URL, api_key=None, timeout=3)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return []
    names = sorted({m["name"] for m in data.get("models", []) if "name" in m})
    return [{"id": name, "name": name} for name in names]


def _openai_compatible_models(base_url: str, api_key: str | None) -> list[dict]:
    data = _fetch_json(f"{base_url}/models", api_key, timeout=5)
    models = [
        {"id": m["id"], "name": m.get("name") or m["id"]}
        for m in data.get("data", [])
        if isinstance(m, dict) and m.get("id")
    ]
    models.sort(key=lambda m: m["name"])
    return models


def _openrouter_models() -> list[dict]:
    data = _fetch_json("https://openrouter.ai/api/v1/models", None, timeout=5)
    free = [
        {"id": m["id"], "name": m.get("name", m["id"])}
        for m in data.get("data", [])
        if isinstance(m, dict)
        and m.get("id")
        and m["id"] != "openrouter/free"
        and _is_free_openrouter_model(m)
    ]
    free.sort(key=lambda m: m["name"])
    return free


def _anthropic_models(api_key: str | None) -> list[dict]:
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    models = [
        {"id": m["id"], "name": m.get("display_name") or m["id"]}
        for m in data.get("data", [])
        if isinstance(m, dict) and m.get("id")
    ]
    models.sort(key=lambda m: m["name"])
    return models


def get_models(
    provider: str,
    api_key: str | None = None,
    db=None,
    force_refresh: bool = False,
) -> list[dict]:
    if provider == "ollama":
        return _ollama_models()

    config = get_provider(provider, db)
    if config is None:
        return []

    if not force_refresh:
        cached = _cached(provider)
        if cached is not None:
            return cached

    try:
        if config.kind == "anthropic":
            return _store(provider, _anthropic_models(api_key))
        if config.base_url is None:
            return []
        if provider == "openrouter":
            return _store(provider, _openrouter_models())
        return _store(
            provider, _openai_compatible_models(config.base_url, api_key)
        )
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        # Return stale cache if we have one, otherwise an empty list
        cached = _cached(provider)
        return cached if cached is not None else []
