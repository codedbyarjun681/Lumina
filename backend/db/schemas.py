from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceReorder(BaseModel):
    ids: list[str] = Field(min_length=1)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceLLMUpdate(BaseModel):
    llm_provider: str = Field(min_length=1, max_length=50)
    llm_model: str = Field(min_length=1, max_length=120)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    llm_provider: str
    llm_model: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    name: str = Field(default="New Conversation", min_length=1, max_length=200)


class ConversationRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ConversationOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    llm_model: str | None = None
    llm_provider: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationLLMUpdate(BaseModel):
    llm_provider: str | None = Field(default=None, min_length=1, max_length=50)
    llm_model: str = Field(min_length=1, max_length=120)


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    needs_api_key: bool = True


class ProviderOut(BaseModel):
    id: str
    name: str
    kind: str
    base_url: str | None
    needs_api_key: bool
    is_builtin: bool

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class ConversationMessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=36)


class MemoryUpdate(BaseModel):
    content: str = Field(min_length=1)


class MemoryOut(BaseModel):
    id: str
    workspace_id: str
    conversation_id: str | None = None
    content: str
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: str
    original_filename: str
    file_size_bytes: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentSearchResult(BaseModel):
    id: str
    original_filename: str
    uploaded_at: datetime
    match_type: str  # "filename" | "content" | "both"
    excerpt: str | None = None


class ApiKeyUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    api_key: str = Field(min_length=1)


class QuizAttemptCreate(BaseModel):
    score: int = Field(ge=0)
    total: int = Field(ge=1)


class QuizOut(BaseModel):
    id: str
    workspace_id: str
    difficulty: str
    num_questions: int
    created_at: datetime
    best_score: int | None = None
    last_score: int | None = None
    attempts: int = 0

    model_config = ConfigDict(from_attributes=True)


class QuizDetailOut(BaseModel):
    id: str
    workspace_id: str
    difficulty: str
    created_at: datetime
    questions: list[dict]
    best_score: int | None = None
    last_score: int | None = None
    attempts: int = 0


class PreferencesUpdate(BaseModel):
    theme: str | None = Field(default=None, min_length=1, max_length=20)
    colorway: str | None = Field(default=None, min_length=1, max_length=50)
    default_provider: str | None = Field(default=None, min_length=1, max_length=50)
    default_model: str | None = Field(default=None, min_length=1, max_length=120)


class SettingsOut(BaseModel):
    api_keys_set: dict[str, bool]
    theme: str | None = None
    colorway: str | None = None
    default_provider: str | None = None
    default_model: str | None = None