from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import crud
from db.database import get_db
from db.schemas import ProviderCreate, ProviderOut
from services.provider_service import list_providers

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
def list_all_providers(db: Session = Depends(get_db)) -> list[ProviderOut]:
    return list_providers(db)


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider(
    data: ProviderCreate, db: Session = Depends(get_db)
) -> ProviderOut:
    return crud.create_provider(
        db, data.name, data.base_url, data.needs_api_key
    )


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id: str, db: Session = Depends(get_db)) -> None:
    if not crud.delete_provider(db, provider_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider not found or is built-in and cannot be removed",
        )
