from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from paths import DB_PATH

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "workspaces" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("workspaces")}

    with engine.begin() as conn:
        if "llm_provider" not in existing_columns:
            conn.execute(
                text(
                    "ALTER TABLE workspaces ADD COLUMN llm_provider "
                    "VARCHAR(20) NOT NULL DEFAULT 'ollama'"
                )
            )
        if "llm_model" not in existing_columns:
            conn.execute(
                text(
                    "ALTER TABLE workspaces ADD COLUMN llm_model "
                    "VARCHAR(120) NOT NULL DEFAULT 'qwen3:8b'"
                )
            )
        if "position" not in existing_columns:
            conn.execute(
                text(
                    "ALTER TABLE workspaces ADD COLUMN position "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )

    if "conversations" in inspector.get_table_names():
        conv_columns = {
            col["name"] for col in inspector.get_columns("conversations")
        }
        with engine.begin() as conn:
            if "llm_model" not in conv_columns:
                conn.execute(
                    text(
                        "ALTER TABLE conversations ADD COLUMN llm_model "
                        "VARCHAR(120)"
                    )
                )
            if "llm_provider" not in conv_columns:
                conn.execute(
                    text(
                        "ALTER TABLE conversations ADD COLUMN llm_provider "
                        "VARCHAR(50)"
                    )
                )

    if "workspace_memory" in inspector.get_table_names():
        memory_columns = {
            col["name"] for col in inspector.get_columns("workspace_memory")
        }
        with engine.begin() as conn:
            if "conversation_id" not in memory_columns:
                conn.execute(
                    text(
                        "ALTER TABLE workspace_memory ADD COLUMN conversation_id "
                        "VARCHAR(36)"
                    )
                )


_BUILTIN_PROVIDERS = [
    ("ollama", "Ollama (local)", "ollama", None, False),
    ("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", True),
    ("opencode", "OpenCode Zen", "openai", "https://opencode.ai/zen/v1", True),
    ("lmstudio", "LM Studio (local)", "openai", "http://localhost:1234/v1", False),
    ("anthropic", "Anthropic", "anthropic", None, True),
]


def _seed_builtin_providers() -> None:
    from sqlalchemy.orm import Session as _Session

    from db.models import Provider

    with _Session(engine) as session:
        for pid, name, kind, base_url, needs_key in _BUILTIN_PROVIDERS:
            if session.get(Provider, pid) is None:
                session.add(
                    Provider(
                        id=pid,
                        name=name,
                        kind=kind,
                        base_url=base_url,
                        needs_api_key=needs_key,
                        is_builtin=True,
                    )
                )
        session.commit()


def init_db() -> None:
    from db import models
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    _seed_builtin_providers()