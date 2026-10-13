from __future__ import annotations

from sqlalchemy.orm import Session


class ProviderConfig:
    def __init__(
        self,
        name: str,
        kind: str,
        base_url: str | None,
        needs_api_key: bool,
        is_builtin: bool = False,
    ) -> None:
        self.name = name
        self.kind = kind                # "ollama" | "openai" | "anthropic"
        self.base_url = base_url        # OpenAI-compatible base URL, if any
        self.needs_api_key = needs_api_key
        self.is_builtin = is_builtin


# In-code failsafe so core flows work even before the DB is seeded.
BUILTIN_PROVIDERS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig("Ollama (local)", "ollama", None, False, True),
    "openrouter": ProviderConfig(
        "OpenRouter", "openai", "https://openrouter.ai/api/v1", True, True
    ),
    "opencode": ProviderConfig(
        "OpenCode Zen", "openai", "https://opencode.ai/zen/v1", True, True
    ),
    "lmstudio": ProviderConfig(
        "LM Studio (local)", "openai", "http://localhost:1234/v1", False, True
    ),
    "anthropic": ProviderConfig("Anthropic", "anthropic", None, True, True),
}

DEFAULT_PROVIDER = "ollama"


def _from_row(row) -> ProviderConfig:
    return ProviderConfig(
        name=row.name,
        kind=row.kind,
        base_url=row.base_url,
        needs_api_key=row.needs_api_key,
        is_builtin=row.is_builtin,
    )


def get_provider(provider_id: str, db: Session | None = None) -> ProviderConfig | None:
    if provider_id in BUILTIN_PROVIDERS:
        return BUILTIN_PROVIDERS[provider_id]

    from db.database import SessionLocal
    from db.models import Provider

    if db is not None:
        row = db.get(Provider, provider_id)
        return _from_row(row) if row is not None else None

    with SessionLocal() as session:
        row = session.get(Provider, provider_id)
        return _from_row(row) if row is not None else None


def list_providers(db: Session) -> list[dict]:
    from db.models import Provider

    rows = db.query(Provider).order_by(Provider.is_builtin.desc(), Provider.name).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "kind": row.kind,
            "base_url": row.base_url,
            "needs_api_key": row.needs_api_key,
            "is_builtin": row.is_builtin,
        }
        for row in rows
    ]
