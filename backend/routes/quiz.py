from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from db.schemas import QuizAttemptCreate, QuizDetailOut, QuizOut
from services import quiz_history_service, quiz_service, settings_service, workspace_service
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

    # Persist the generated quiz so it can be retaken / scored later
    saved = await asyncio.to_thread(
        quiz_history_service.save_quiz,
        db,
        workspace.id,
        questions,
        data.difficulty,
    )
    return {"questions": questions, "quiz_id": saved.id}


@router.get("/workspaces/{workspace_id}/quizzes", response_model=list[QuizOut])
def list_quizzes(
    workspace_id: str, db: Session = Depends(get_db)
) -> list[QuizOut]:
    if workspace_service.get_workspace(db, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return quiz_history_service.list_quizzes(db, workspace_id)


@router.get("/quizzes/{quiz_id}", response_model=QuizDetailOut)
def get_quiz(quiz_id: str, db: Session = Depends(get_db)) -> QuizDetailOut:
    detail = quiz_history_service.get_quiz_detail(db, quiz_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )
    return detail


@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(quiz_id: str, db: Session = Depends(get_db)) -> None:
    if not quiz_history_service.delete_quiz(db, quiz_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def record_attempt(
    quiz_id: str, data: QuizAttemptCreate, db: Session = Depends(get_db)
) -> QuizDetailOut:
    if data.total > 0 and data.score > data.total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Score cannot exceed total",
        )
    detail = quiz_history_service.record_attempt(db, quiz_id, data.score, data.total)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )
    return detail
