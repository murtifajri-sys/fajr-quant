"""Telegram settings + test send."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import MessageOut, TelegramSettingCreate, TelegramSettingOut
from app.core.db import get_db
from app.models.setting import TelegramSetting
from app.services.notifier.telegram import send_test_message

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("", response_model=list[TelegramSettingOut])
def list_settings(db: Session = Depends(get_db)):
    return db.execute(select(TelegramSetting)).scalars().all()


@router.post("", response_model=TelegramSettingOut)
def upsert(payload: TelegramSettingCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(TelegramSetting).where(TelegramSetting.label == payload.label)
    ).scalar_one_or_none()
    if existing:
        existing.chat_id = payload.chat_id
        existing.enabled = payload.enabled
        existing.daily_digest_time = payload.daily_digest_time
        db.commit()
        db.refresh(existing)
        return existing
    row = TelegramSetting(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{setting_id}/test", response_model=MessageOut)
def test_send(setting_id: int, db: Session = Depends(get_db)):
    row = db.get(TelegramSetting, setting_id)
    if not row:
        raise HTTPException(404, "Setting not found")
    ok = send_test_message(row.chat_id)
    return MessageOut(message="Sent" if ok else "Failed", detail=ok)
