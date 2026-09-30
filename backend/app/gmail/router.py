import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.common import utcnow
from app.config import get_settings
from app.db import DbSession
from app.gmail.client import SCOPE, connection
from app.gmail.models import GmailMessage
from app.google import oauth
from app.growth.locking import WRITE_LOCK
from app.sources.runner import SourceReport, run_gmail

router = APIRouter(prefix="/gmail", tags=["gmail"])


class GmailStatus(BaseModel):
    configured: bool  # Google OAuth client in .env
    llm_configured: bool  # without the LLM, labelled mail is never read
    enabled: bool  # "gmail" in SOURCES_ENABLED
    state: str
    detail: str | None
    label: str
    processed: int  # messages already read (each is sent to the LLM once)


class ConnectOut(BaseModel):
    authorization_url: str


@router.get("/status", response_model=GmailStatus)
def status(session: DbSession):
    settings = get_settings()
    row = connection(session)
    return GmailStatus(
        configured=oauth.configured(settings),
        llm_configured=bool(settings.llm_base_url),
        enabled="gmail" in settings.enabled_sources,
        state=row.state,
        detail=row.detail,
        label=settings.gmail_label,
        processed=session.scalar(select(func.count()).select_from(GmailMessage)) or 0,
    )


@router.post("/connect", response_model=ConnectOut)
def connect(session: DbSession):
    settings = get_settings()
    with WRITE_LOCK:
        url = oauth.begin(
            session, connection(session), settings, SCOPE, settings.google_gmail_redirect_uri
        )
        return ConnectOut(authorization_url=url)


@router.get("/callback", include_in_schema=False)
def callback(session: DbSession, state: str = "", code: str = "", error: str | None = None):
    settings = get_settings()
    with WRITE_LOCK:
        if error or not code:
            raise HTTPException(400, "Připojení Gmailu bylo zrušeno. Vrať se do growthOS.")
        row = connection(session)
        try:
            with httpx.Client(timeout=20) as client:
                oauth.finish(
                    session,
                    row,
                    settings,
                    SCOPE,
                    settings.google_gmail_redirect_uri,
                    state,
                    code,
                    client,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Google neodpovídá. Připoj Gmail znovu.") from exc
        row.state = "connected"
        session.commit()
        return RedirectResponse(
            settings.frontend_url.rstrip("/") + "/growth?tab=gmail", status_code=303
        )


@router.post("/disconnect", response_model=GmailStatus)
def disconnect(session: DbSession):
    with WRITE_LOCK:
        row = connection(session)
        row.protected_tokens = row.protected_oauth = None
        row.state = "disconnected"
        row.detail = None
        session.commit()
        return status(session)


@router.post("/run", response_model=SourceReport)
def run(session: DbSession):
    """Read new labelled messages now (also part of every source run)."""
    if "gmail" not in get_settings().enabled_sources:
        raise HTTPException(409, "Gmail není v SOURCES_ENABLED.")
    return run_gmail(session, utcnow())
