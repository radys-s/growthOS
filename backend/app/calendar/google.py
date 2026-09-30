import uuid
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.calendar.models import CalendarConnection
from app.config import get_settings
from app.google import oauth

SCOPE = "https://www.googleapis.com/auth/calendar.app.created"


def connection(session: Session) -> CalendarConnection:
    return oauth.single_row(session, CalendarConnection)


def begin(session: Session) -> str:
    settings = get_settings()
    return oauth.begin(session, connection(session), settings, SCOPE, settings.google_redirect_uri)


def finish(session: Session, state: str, code: str, client: httpx.Client):
    settings = get_settings()
    row = connection(session)
    oauth.finish(session, row, settings, SCOPE, settings.google_redirect_uri, state, code, client)
    row.state = (
        "connected"
        if row.calendar_id
        else "creation_pending"
        if row.metadata_json.get("creation_pending")
        else "needs_calendar"
    )
    session.commit()


class GoogleCalendar:
    def __init__(self, session: Session, client: httpx.Client):
        self.session, self.client = session, client
        self.row = connection(session)

    def token(self) -> str:
        return oauth.access_token(self.session, self.row, get_settings(), self.client)

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = "Bearer " + self.token()
        response = self.client.request(
            method, "https://www.googleapis.com/calendar/v3/" + path, headers=headers, **kwargs
        )
        return oauth.checked(self.session, self.row, response)

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
