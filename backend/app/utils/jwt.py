"""Read non-sensitive JWT metadata without validating its signature."""
import base64
import json
from datetime import datetime, timezone


def jwt_expiry(token: str) -> datetime | None:
    """Return the JWT ``exp`` as a naive UTC datetime, if present."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return datetime.fromtimestamp(int(claims["exp"]), timezone.utc).replace(
            tzinfo=None
        )
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
