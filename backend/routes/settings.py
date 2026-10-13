from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.schemas import ApiKeyUpdate, PreferencesUpdate, SettingsOut
from services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    prefs = settings_service.get_preferences(db)
    return SettingsOut(
        api_keys_set=settings_service.providers_key_status(db),
        theme=prefs["theme"],
        colorway=prefs["colorway"],
        default_provider=prefs["default_provider"],
        default_model=prefs["default_model"],
    )


@router.put("/preferences", status_code=204)
def set_preferences(data: PreferencesUpdate, db: Session = Depends(get_db)) -> None:
    settings_service.set_preferences(db, data.model_dump(exclude_none=True))


@router.put("/api-key", status_code=204)
def set_api_key(data: ApiKeyUpdate, db: Session = Depends(get_db)) -> None:
    settings_service.set_api_key(db, data.provider, data.api_key)
