from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from services import quiz_service, settings_service, workspace_service
from services.provider_service import get_provider

router = APIRouter(tags=["quiz"])


class QuizRequest(BaseModel):
    num_questions: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


@router.post("/workspaces/{workspace_id}/quiz")
async def create_quiz(
    workspace_id: str,
    data: QuizRequest,
    db: Session = Depends(get_db),
) -> dict:
    workspace = workspace_service.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )

    api_key = None
    effective_provider, effective_model = settings_service.resolve_llm(
        db, None, None, workspace.llm_provider, workspace.llm_model
    )
    provider_config = get_provider(effective_provider, db)
    if provider_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown LLM provider: {effective_provider}",
        )
    if provider_config.needs_api_key:
        api_key = settings_service.get_api_key(db, effective_provider)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider {provider_config.name} has no API key configured "
                    "in Settings."
                ),
            )

    questions = await asyncio.to_thread(
        quiz_service.generate_quiz,
        workspace.id,
        effective_provider,
        effective_model,
        api_key,
        data.num_questions,
        data.difficulty,
    )
    return {"questions": questions}
