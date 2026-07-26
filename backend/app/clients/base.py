"""Base HTTP client with retry, rate-limit, token injection."""
from datetime import datetime

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


from app.core.config import settings
from app.core.logging import log
from app.models.setting import StockbitToken
from app.utils.encryption import decrypt


class TokenExpiredError(Exception):
    """Raised when Stockbit returns 401 / token JWT expired."""


class NoActiveTokenError(Exception):
    pass


def get_active_token(db: Session) -> tuple[StockbitToken, str]:
    row = db.execute(
        select(StockbitToken).where(StockbitToken.active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if not row:
        raise NoActiveTokenError("No active Stockbit token. Please input one via UI.")
    token = decrypt(row.encrypted_token)
    return row, token


def mark_token_used(db: Session, token_row: StockbitToken, ok: bool, err: str | None = None):
    """Update token last_used_at without read-modify-write race condition.

    Multiple workers may call this concurrently for the same token row.
    We use a raw SQL UPDATE with retry to survive MariaDB lock conflicts.
    """
    last_error = None
    if not ok and err and (
        "expired" in err.lower()
        or "401" in err
        or "unauthorized" in err.lower()
    ):
        last_error = err
        if token_row.last_error is None:
            try:
                from app.services.notifier.telegram import send_token_expired_alert
                send_token_expired_alert(db, detail=err[:200])
            except Exception:
                pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.5, max=4),
        retry=retry_if_exception_type(OperationalError),
        reraise=True,
    )
    def _do_update():
        db.execute(
            update(StockbitToken)
            .where(StockbitToken.id == token_row.id)
            .values(
                last_used_at=datetime.utcnow(),
                last_error=last_error,
            )
        )
        db.commit()

    try:
        _do_update()
    except Exception as exc:
        log.warning("token_update_failed", token_id=token_row.id, error=str(exc))
        try:
            db.rollback()
        except Exception:
            pass


class BaseClient:
    def __init__(self, base_url: str = settings.STOCKBIT_BASE_URL, db: Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.db = db
        self._client = httpx.Client(
            timeout=settings.STOCKBIT_REQUEST_TIMEOUT,
            headers={
                "accept": "application/json, text/plain, */*",
                "origin": "https://stockbit.com",
                "referer": "https://stockbit.com/",
                "user-agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
                ),
                "x-platform": "web",
            },
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @retry(
        stop=stop_after_attempt(settings.STOCKBIT_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _request(self, method: str, path: str, token: str, params: dict | None = None) -> dict:
        headers = {"authorization": f"Bearer {token}"}
        url = f"{self.base_url}{path}"
        resp = self._client.request(method, url, params=params, headers=headers)
        if resp.status_code == 401:
            raise TokenExpiredError("Stockbit token expired (401).")
        resp.raise_for_status()
        return resp.json()
