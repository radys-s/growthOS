"""Three-way synchronization, scoped to our dedicated calendar and owned event IDs."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.calendar.google import GoogleCalendar
from app.growth.locking import WRITE_LOCK
from app.growth.models import PlannedAction

SYNC_RUNNING = threading.Lock()
WRITE_WAIT_SECONDS = 30


class SkipPlan(Exception):
    """This plan cannot be synchronized now; the others still can."""


def _utc(value: datetime) -> str:
    # Google stores whole seconds; comparing microseconds would report phantom changes.
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def stamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Calendar time requires an offset")
    return _utc(parsed)


def local_value(plan: PlannedAction) -> dict | None:
    if not plan.starts_at or plan.status == "cancelled":
        return None
    return {
        "title": plan.title,
        "description": plan.description,
        "starts_at": _utc(plan.starts_at),
        "ends_at": _utc(plan.ends_at),
    }


def remote_value(event: dict) -> dict | None:
    if event.get("status") == "cancelled":
        return None
    start, end = event.get("start", {}), event.get("end", {})
    if "dateTime" not in start or "dateTime" not in end:
        raise ValueError("Celodenní událost nemá přesný čas. V Google nastav čas začátku a konce.")
    value = {
        "title": event.get("summary", "Bez názvu"),
        "description": event.get("description", ""),
        "starts_at": stamp(start["dateTime"]),
        "ends_at": stamp(end["dateTime"]),
    }
    if (
        len(value["title"]) > 300
        or len(value["description"]) > 10000
        or value["ends_at"] <= value["starts_at"]
    ):
        raise ValueError("Událost obsahuje nepodporované hodnoty.")
    return value


def body(plan: PlannedAction, value: dict) -> dict:
    return {
        "id": plan.calendar_event_id,
        "summary": value["title"],
        "description": value["description"],
        "start": {"dateTime": value["starts_at"], "timeZone": "Europe/Prague"},
        "end": {"dateTime": value["ends_at"], "timeZone": "Europe/Prague"},
        "extendedProperties": {"private": {"growthos_plan": str(plan.id)}},
    }


def apply_remote(plan: PlannedAction, value: dict | None):
    if value is None:
        plan.starts_at = plan.ends_at = None
        plan.calendar_event_id = None
    else:
        plan.title, plan.description = value["title"], value["description"]
        plan.starts_at = datetime.fromisoformat(value["starts_at"])
        plan.ends_at = datetime.fromisoformat(value["ends_at"])
        day = plan.starts_at.astimezone(ZoneInfo("Europe/Prague")).date()
        plan.week_of = day - timedelta(days=day.weekday())
    plan.sync_base = value
    plan.conflict = None


def synchronize(api: GoogleCalendar, resolution: tuple[uuid.UUID, str] | None = None) -> dict:
    if not SYNC_RUNNING.acquire(blocking=False):
        raise HTTPException(409, "Synchronizace již běží.")
    try:
        if not WRITE_LOCK.acquire(timeout=WRITE_WAIT_SECONDS):
            raise HTTPException(409, "Právě probíhá jiná změna. Zkus synchronizaci za chvíli.")
        try:
            return _synchronize(api, resolution)
        finally:
            WRITE_LOCK.release()
    finally:
        SYNC_RUNNING.release()


def _fetch(api: GoogleCalendar, plan: PlannedAction, path: str) -> tuple[dict | None, dict | None]:
    response = api.request("GET", path)
    if response.status_code in (404, 410):
        return None, None
    if response.status_code != 200:
        raise HTTPException(502, "Google událost nelze načíst.")
    event = response.json()
    owner = event.get("extendedProperties", {}).get("private", {}).get("growthos_plan")
    if event.get("status") != "cancelled" and owner != str(plan.id):
        raise SkipPlan(f"„{plan.title}“: událost nemá označení growthOS; nebudeme ji měnit.")
    try:
        return event, remote_value(event)
    except ValueError as exc:
        raise SkipPlan(f"„{plan.title}“: {exc}") from exc


def _synchronize(api: GoogleCalendar, resolution: tuple[uuid.UUID, str] | None) -> dict:
    api.session.expire_all()
    api.check()
    changed = conflicts = 0
    skipped: list[str] = []
    plans = list(api.session.scalars(select(PlannedAction)))
    for plan in plans:
        if resolution and plan.id != resolution[0]:
            continue
        local = local_value(plan)
        if not plan.calendar_event_id and local is None:
            continue
        if not plan.calendar_event_id:
            # Persist before the request: network retries reuse the same event ID.
            plan.calendar_event_id = uuid.uuid4().hex
            api.session.commit()
        path = api.path("/events/" + plan.calendar_event_id)
        try:
            event, remote = _fetch(api, plan, path)
        except SkipPlan as exc:
            if resolution:
                raise HTTPException(409, str(exc)) from exc
            skipped.append(str(exc))
            continue
        base = plan.sync_base
        if local == remote:
            plan.sync_base, plan.conflict = local, None
            if local is None:
                plan.calendar_event_id = None
            api.session.commit()
            continue
        both_changed = local != base and remote != base
        if plan.conflict and resolution:
            if plan.conflict.get("remote") != remote or plan.conflict.get("local") != local:
                plan.conflict = {"local": local, "remote": remote}
                api.session.commit()
                raise HTTPException(409, "Od zobrazení konfliktu se data změnila. Vyber znovu.")
            choose_remote = resolution[1] == "google"
        elif both_changed or plan.conflict:
            plan.conflict = {"local": local, "remote": remote}
            conflicts += 1
            api.session.commit()
            continue
        else:
            choose_remote = remote != base
        if choose_remote:
            apply_remote(plan, remote)
        elif local is None:
            if event and remote is not None:
                result = api.request("DELETE", path, headers={"If-Match": event["etag"]})
                if result.status_code not in (204, 404, 410):
                    raise HTTPException(409, "Událost se změnila; zopakuj synchronizaci.")
            plan.calendar_event_id = None
            plan.sync_base, plan.conflict = None, None
        else:
            if event is None or remote is None:
                if event is not None or base is not None:
                    plan.calendar_event_id = uuid.uuid4().hex
                    api.session.commit()
                    path = api.path("/events/" + plan.calendar_event_id)
                result = api.request("POST", api.path("/events"), json=body(plan, local))
                if result.status_code == 409:
                    # The ID already exists: an earlier insert landed but its answer was lost.
                    try:
                        event, remote = _fetch(api, plan, path)
                    except SkipPlan:
                        event, remote = None, None
                    if remote == local:
                        result = httpx.Response(200)
            else:
                payload = body(plan, local)
                payload.pop("id")
                result = api.request(
                    "PATCH", path, json=payload, headers={"If-Match": event["etag"]}
                )
            if result.status_code not in (200, 201):
                raise HTTPException(
                    409,
                    "Zápis nebyl potvrzen. Zopakuj synchronizaci; data zůstávají zachována.",
                )
            plan.sync_base, plan.conflict = local, None
        changed += 1
        api.session.commit()
    return {"changed": changed, "conflicts": conflicts, "skipped": skipped}
