"""Token management routes: input/refresh Stockbit token."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import MessageOut, TokenCreate, TokenOut
from app.core.db import get_db
from app.models.setting import StockbitToken
from app.utils.encryption import encrypt
from app.utils.jwt import jwt_expiry

router = APIRouter(prefix="/tokens", tags=["tokens"])


def _to_out(token: StockbitToken) -> TokenOut:
    expired = bool(token.expires_at and token.expires_at <= datetime.utcnow())
    if expired:
        status = "expired"
    elif token.active:
        status = "active"
    elif token.last_error:
        status = "error"
    else:
        status = "inactive"
    warning = token.last_error if (not token.active and token.last_error) else None
    return TokenOut(
        id=token.id,
        label=token.label,
        expires_at=token.expires_at,
        active=token.active,
        last_used_at=token.last_used_at,
        last_error=token.last_error,
        token_preview="stored",
        status=status,
        is_expired=expired,
        warning=warning,
    )


@router.get("", response_model=list[TokenOut])
def list_tokens(db: Session = Depends(get_db)):
    rows = db.query(StockbitToken).order_by(StockbitToken.id.desc()).all()
    return [_to_out(token) for token in rows]


@router.post("", response_model=TokenOut)
def create_token(payload: TokenCreate, db: Session = Depends(get_db)):
    token_str = payload.token.strip()
    computed_expiry = payload.expires_at or jwt_expiry(token_str)

    if computed_expiry and computed_expiry <= datetime.utcnow():
        raise HTTPException(400, "Token sudah expired. Gunakan token yang masih berlaku.")

    # Deactivate previous tokens with same label
    db.query(StockbitToken).filter(StockbitToken.label == payload.label).update(
        {"active": False}
    )
    token = StockbitToken(
        label=payload.label,
        encrypted_token=encrypt(token_str),
        expires_at=computed_expiry,
        active=True,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return _to_out(token)


@router.delete("/{token_id}", response_model=MessageOut)
def delete_token(token_id: int, db: Session = Depends(get_db)):
    token = db.get(StockbitToken, token_id)
    if not token:
        raise HTTPException(404, "Token not found")
    db.delete(token)
    db.commit()
    return MessageOut(message="Token deleted")


@router.post("/{token_id}/activate", response_model=MessageOut)
def activate_token(token_id: int, db: Session = Depends(get_db)):
    token = db.get(StockbitToken, token_id)
    if not token:
        raise HTTPException(404, "Token not found")
    db.query(StockbitToken).filter(StockbitToken.label == token.label).update(
        {"active": False}
    )
    token.active = True
    db.commit()
    return MessageOut(message="Token activated")


@router.post("/{token_id}/test", response_model=MessageOut)
def test_token(token_id: int, db: Session = Depends(get_db)):
    token = db.get(StockbitToken, token_id)
    if not token:
        raise HTTPException(404, "Token not found")

    from app.clients.stockbit import StockbitClient

    db.query(StockbitToken).update({"active": False})
    token.active = True
    db.commit()
    try:
        with StockbitClient(db=db) as client:
            client.get_company_profile("BBCA")
    except Exception as exc:
        raise HTTPException(502, f"Stockbit connection failed: {exc}") from exc
    return MessageOut(message="Stockbit token is valid")
