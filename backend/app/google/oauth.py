"""Google OAuth (authorization code + PKCE) shared by the calendar and Gmail grants.

Each integration keeps its own single-row connection table and its own minimal scope, so the
grants can be revoked independently (ADR 0008, 0009). Tokens are stored DPAPI-protected.
"""

import base64
import hashlib
import secrets
import time
from typing import Protocol
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendar.vault import protect, reveal
from app.config import Settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# 403 reasons that mean "slow down", not "missing permission"
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}


class Connection(Protocol):
    protected_tokens: str | None
    protected_oauth: str | None
    state: str
    detail: str | None


def single_row[T](session: Session, model: type[T]) -> T:
    """Get or create the id=1 connection row; tolerates a concurrent first request."""
    row = session.get(model, 1)
    if row is None:
        session.add(model(id=1))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        row = session.get(model, 1)
    return row


def error_reason(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
    except ValueError:
        return ""
    if isinstance(error, str):  # token endpoint: {"error": "invalid_grant"}
        return error
    errors = error.get("errors") or [{}]
    return errors[0].get("reason", "") if isinstance(errors[0], dict) else ""


def configured(settings: Settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def begin(
    session: Session, row: Connection, settings: Settings, scope: str, redirect_uri: str
) -> str:
    if not configured(settings):
        raise HTTPException(409, "Doplň GOOGLE_CLIENT_ID a GOOGLE_CLIENT_SECRET v backend/.env.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    row.protected_oauth = protect(
        {"state": state, "verifier": verifier, "expires": time.time() + 600}
    )
    session.commit()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    return (
        AUTH_URL
        + "?"
        + urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": scope,
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )


def finish(
    session: Session,
    row: Connection,
    settings: Settings,
    scope: str,
    redirect_uri: str,
    state: str,
    code: str,
    client: httpx.Client,
) -> None:
    """Exchange the code; on success the row holds protected tokens (caller sets row.state)."""
    pending = reveal(row.protected_oauth) if row.protected_oauth else {}
    expected = pending.get("state", "")
    if (
        not expected
        or not secrets.compare_digest(state.encode(), expected.encode())
        or pending.get("expires", 0) < time.time()
    ):
        raise HTTPException(400, "Přihlášení vypršelo nebo má neplatný stav. Připoj účet znovu.")
    row.protected_oauth = None
    session.commit()
    response = client.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": pending["verifier"],
        },
    )
    if response.status_code != 200:
        raise HTTPException(400, "Google přihlášení nebylo dokončeno. Připoj účet znovu.")
    token = response.json()
    if scope not in token.get("scope", "").split():
        raise HTTPException(400, "Google neudělil požadované oprávnění.")
    if not token.get("refresh_token"):
        raise HTTPException(400, "Google nevrátil oprávnění pro obnovení. Připoj účet znovu.")
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    row.protected_tokens = protect(token)
    row.detail = None


def access_token(
    session: Session, row: Connection, settings: Settings, client: httpx.Client
) -> str:
    if not row.protected_tokens:
        raise HTTPException(409, "Nejdřív připoj Google účet.")
    token = reveal(row.protected_tokens)
    if token.get("expires_at", 0) >= time.time() + 60:
        return token["access_token"]
    response = client.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token.get("refresh_token", ""),
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
        },
    )
    if response.status_code in (400, 401) and error_reason(response) == "invalid_grant":
        row.state = "reauthorize"
        session.commit()
        raise HTTPException(409, "Platnost přihlášení skončila. Připoj Google znovu.")
    if response.status_code != 200:
        if response.status_code < 500:
            raise HTTPException(
                409, "Google odmítl údaje aplikace. Zkontroluj GOOGLE_CLIENT_* v .env."
            )
        raise HTTPException(503, "Google přihlášení je dočasně nedostupné. Zkus později.")
    try:
        fresh = response.json()
    except ValueError:
        fresh = {}
    if not fresh.get("access_token"):
        raise HTTPException(503, "Google vrátil neúplnou odpověď. Zkus později.")
    token.update(fresh)
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    row.protected_tokens = protect(token)
    session.commit()
    return token["access_token"]


def checked(session: Session, row: Connection, response: httpx.Response) -> httpx.Response:
    """Map Google API auth/limit errors: 401 or permission 403 → reauthorize, else transient."""
    if response.status_code == 401 or (
        response.status_code == 403 and error_reason(response) not in RATE_LIMIT_REASONS
    ):
        row.state = "reauthorize"
        session.commit()
        raise HTTPException(409, "Google odepřel přístup. Připoj správný účet znovu.")
    if response.status_code in (403, 429) or response.status_code >= 500:
        raise HTTPException(503, "Google je dočasně nedostupný. Zkus to později.")
    return response
