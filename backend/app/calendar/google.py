import base64
import hashlib
import secrets
import time
import uuid
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendar.models import CalendarConnection
from app.calendar.vault import protect, reveal
from app.config import get_settings

SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# 403 reasons that mean "slow down", not "missing permission"
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}


def connection(session: Session) -> CalendarConnection:
    row = session.get(CalendarConnection, 1)
    if row is None:
        session.add(CalendarConnection(id=1))
        try:
            session.commit()
        except IntegrityError:  # a concurrent first request created it
            session.rollback()
        row = session.get(CalendarConnection, 1)
    return row


def _error_reason(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
    except ValueError:
        return ""
    if isinstance(error, str):  # OAuth token endpoint: {"error": "invalid_grant"}
        return error
    errors = error.get("errors") or [{}]
    return errors[0].get("reason", "") if isinstance(errors[0], dict) else ""


def begin(session: Session) -> str:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(409, "Doplň GOOGLE_CLIENT_ID a GOOGLE_CLIENT_SECRET v backend/.env.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    row = connection(session)
    row.protected_oauth = protect(
        {"state": state, "verifier": verifier, "expires": time.time() + 600}
    )
    session.commit()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )


def finish(session: Session, state: str, code: str, client: httpx.Client):
    row = connection(session)
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
    settings = get_settings()
    response = client.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "code_verifier": pending["verifier"],
        },
    )
    if response.status_code != 200:
        raise HTTPException(400, "Google přihlášení nebylo dokončeno. Připoj účet znovu.")
    token = response.json()
    if SCOPE not in token.get("scope", "").split():
        raise HTTPException(400, "Google neudělil požadované oprávnění.")
    if not token.get("refresh_token"):
        raise HTTPException(400, "Google nevrátil oprávnění pro obnovení. Připoj účet znovu.")
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    row.protected_tokens = protect(token)
    row.state = (
        "connected"
        if row.calendar_id
        else "creation_pending"
        if row.metadata_json.get("creation_pending")
        else "needs_calendar"
    )
    row.detail = None
    session.commit()


class GoogleCalendar:
    def __init__(self, session: Session, client: httpx.Client):
        self.session, self.client = session, client
        self.row = connection(session)

    def token(self) -> str:
        if not self.row.protected_tokens:
            raise HTTPException(409, "Nejdřív připoj Google účet.")
        token = reveal(self.row.protected_tokens)
        if token.get("expires_at", 0) < time.time() + 60:
            settings = get_settings()
            response = self.client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.get("refresh_token", ""),
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                },
            )
            if response.status_code in (400, 401) and _error_reason(response) == "invalid_grant":
                self.row.state = "reauthorize"
                self.session.commit()
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
            self.row.protected_tokens = protect(token)
            self.session.commit()
        return token["access_token"]

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = "Bearer " + self.token()
        response = self.client.request(
            method, "https://www.googleapis.com/calendar/v3/" + path, headers=headers, **kwargs
        )
        if response.status_code == 401:
            self.row.state = "reauthorize"
            self.session.commit()
            raise HTTPException(409, "Připoj Google účet znovu.")
        if response.status_code == 403 and _error_reason(response) not in RATE_LIMIT_REASONS:
            self.row.state = "reauthorize"
            self.session.commit()
            raise HTTPException(409, "Google odepřel přístup. Připoj správný účet znovu.")
        if response.status_code in (403, 429) or response.status_code >= 500:
            raise HTTPException(503, "Google synchronizace je dočasně nedostupná. Zkus ji později.")
        return response

    def path(self, suffix: str = "") -> str:
        if not self.row.calendar_id:
            raise HTTPException(409, "Vytvoř vyhrazený growthOS kalendář.")
        return "calendars/" + quote(self.row.calendar_id, safe="") + suffix

    def check(self):
        response = self.request("GET", self.path())
        if response.status_code == 404:
            self.row.state = "calendar_missing"
            self.session.commit()
            raise HTTPException(409, "Kalendář chybí nebo patří jinému účtu. Připoj původní účet.")
        if response.status_code != 200:
            raise HTTPException(502, "Kalendář nelze ověřit.")

    def create(self):
        if self.row.calendar_id:
            self.check()
            return
        if self.row.state == "creation_pending":
            raise HTTPException(
                409, "Výsledek vytvoření není známý. Neopakujeme jej kvůli duplicitám."
            )
        self.token()
        self.row.state = "creation_pending"
        self.row.metadata_json = {
            **self.row.metadata_json,
            "creation_pending": True,
            "marker": self.row.metadata_json.get("marker") or uuid.uuid4().hex,
        }
        self.session.commit()
        try:
            response = self.request(
                "POST",
                "calendars",
                json={
                    "summary": "growthOS",
                    "timeZone": "Europe/Prague",
                    "description": "growthOS integration " + self.row.metadata_json["marker"],
                },
            )
        except HTTPException as exc:
            if exc.status_code == 409:  # 401/403: Google refused, nothing was created
                self._abandon_creation(self.row.state)
            raise
        if response.status_code != 200:
            # A definite client error means nothing was created; unblock a new attempt.
            if 400 <= response.status_code < 500:
                self._abandon_creation("needs_calendar")
            raise HTTPException(502, "Vytvoření kalendáře nebylo potvrzeno.")
        self.row.calendar_id = response.json()["id"]
        self.row.state = "connected"
        self.row.metadata_json = {**self.row.metadata_json, "creation_pending": False}
        self.session.commit()

    def _abandon_creation(self, state: str):
        self.row.state = state
        self.row.metadata_json = {**self.row.metadata_json, "creation_pending": False}
        self.session.commit()
