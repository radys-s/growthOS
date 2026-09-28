import uuid
from typing import Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.calendar.google import GoogleCalendar, begin, connection, finish
from app.calendar.sync import synchronize
from app.config import get_settings
from app.db import DbSession
from app.growth.locking import WRITE_LOCK
from app.growth.models import PlannedAction
from app.growth.schemas import PlanOut

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarStatus(BaseModel):
    configured: bool
    state: str
    detail: str | None
    has_calendar: bool


class ConnectOut(BaseModel):
    authorization_url: str


class SyncOut(BaseModel):
    changed: int
    conflicts: int


class ResolveIn(BaseModel):
    choice: Literal["local", "google"]


@router.get("/status", response_model=CalendarStatus)
def status(session: DbSession):
    row = connection(session)
    settings = get_settings()
    return CalendarStatus(
        configured=bool(settings.google_client_id and settings.google_client_secret),
        state=row.state,
        detail=row.detail,
        has_calendar=bool(row.calendar_id),
    )


@router.post("/connect", response_model=ConnectOut)
def connect(session: DbSession):
    with WRITE_LOCK:
        return ConnectOut(authorization_url=begin(session))


@router.get("/callback", include_in_schema=False)
def callback(session: DbSession, state: str = "", code: str = "", error: str | None = None):
    with WRITE_LOCK:
        if error or not code:
            raise HTTPException(
                400, "Google připojení bylo zrušeno. Vrať se do nastavení growthOS."
            )
        try:
            with httpx.Client(timeout=20) as client:
                finish(session, state, code, client)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Google neodpovídá. Připoj účet znovu.") from exc
        return RedirectResponse("http://localhost:3000/growth?tab=calendar", status_code=303)


@router.post("/create", response_model=CalendarStatus)
def create(session: DbSession):
    with WRITE_LOCK:
        try:
            with httpx.Client(timeout=20) as client:
                GoogleCalendar(session, client).create()
        except httpx.HTTPError as exc:
            raise HTTPException(
                503, "Výsledek vytvoření není známý. Automaticky jej neopakujeme."
            ) from exc
        return status(session)


@router.post("/sync", response_model=SyncOut)
def sync(session: DbSession):
    try:
        with httpx.Client(timeout=20) as client:
            return synchronize(GoogleCalendar(session, client))
    except httpx.HTTPError as exc:
        raise HTTPException(
            503, "Spojení přerušeno. Synchronizaci lze bezpečně zopakovat."
        ) from exc


@router.post("/conflicts/{plan_id}", response_model=SyncOut)
def resolve(plan_id: uuid.UUID, data: ResolveIn, session: DbSession):
    plan = session.get(PlannedAction, plan_id)
    if not plan or not plan.conflict:
        raise HTTPException(404, "Konflikt nenalezen.")
    try:
        with httpx.Client(timeout=20) as client:
            return synchronize(GoogleCalendar(session, client), (plan_id, data.choice))
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Spojení přerušeno. Zkus synchronizaci znovu.") from exc


@router.post("/disconnect", response_model=CalendarStatus)
def disconnect(session: DbSession):
    with WRITE_LOCK:
        row = connection(session)
        row.protected_tokens = row.protected_oauth = None
        row.state = "disconnected"
        session.commit()
        return status(session)


@router.get("/conflicts", response_model=list[PlanOut])
def conflicts(session: DbSession):
    return list(session.scalars(select(PlannedAction).where(PlannedAction.conflict.is_not(None))))


class RecoverIn(BaseModel):
    calendar_id: str = Field(min_length=1, max_length=500)


@router.post("/recover", response_model=CalendarStatus)
def recover(data: RecoverIn, session: DbSession):
    with WRITE_LOCK:
        row = connection(session)
        marker = row.metadata_json.get("marker")
        if not marker or row.calendar_id:
            raise HTTPException(409, "Není žádné nedokončené vytvoření kalendáře.")
        try:
            with httpx.Client(timeout=20) as client:
                api = GoogleCalendar(session, client)
                response = api.request("GET", "calendars/" + quote(data.calendar_id, safe=""))
                if (
                    response.status_code != 200
                    or response.json().get("description") != "growthOS integration " + marker
                ):
                    raise HTTPException(
                        409, "Tento kalendář nebyl vytvořen tímto připojením growthOS."
                    )
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Kalendář nelze ověřit. Zkus později.") from exc
        row.calendar_id = data.calendar_id
        row.state = "connected"
        row.metadata_json = {**row.metadata_json, "creation_pending": False}
        session.commit()
        return status(session)


class ReplaceIn(BaseModel):
    confirmed: Literal[True]


@router.post("/replace-missing", response_model=CalendarStatus)
def replace_missing(data: ReplaceIn, session: DbSession):
    with WRITE_LOCK:
        row = connection(session)
        if row.state != "calendar_missing":
            raise HTTPException(409, "Kalendář není označen jako chybějící.")
        row.calendar_id = None
        row.metadata_json = {}
        row.state = "needs_calendar"
        for plan in session.scalars(select(PlannedAction)):
            plan.calendar_event_id = None
            plan.sync_base = None
            plan.conflict = None
        session.commit()
        return status(session)
