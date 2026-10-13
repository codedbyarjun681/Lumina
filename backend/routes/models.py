from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.database import get_db
from services import models_service, settings_service
from services.provider_service import get_provider, list_providers

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/providers")
def providers(db: Session = Depends(get_db)) -> dict:
    return {"providers": list_providers(db)}


@router.get("/{provider}")
def list_provider_models(
    provider: str, db: Session = Depends(get_db)
) -> dict:
    config = get_provider(provider, db)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider: {provider}",
        )
    api_key = settings_service.get_api_key(db, provider)
    return {"models": models_service.get_models(provider, api_key, db)}
