import copy
import time
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import HTTPException

from app.calendar.google import GoogleCalendar, connection
from app.calendar.sync import apply_remote, local_value, remote_value, synchronize
from app.calendar.vault import protect, reveal
from app.growth.models import PlannedAction
from app.profile.service import get_or_create_profile


class FakeGoogle:
    def __init__(self, session):
        self.session = session
        self.events = {}
        self.writes = 0
        self.lose_response = False

    def check(self):
        pass

    def path(self, suffix=""):
        return "dedicated" + suffix

    def request(self, method, path, **kwargs):
        event_id = path.rsplit("/", 1)[-1]
        if method == "GET":
            return (
                httpx.Response(200, json=self.events[event_id])
                if event_id in self.events
                else httpx.Response(404)
            )
        self.writes += 1
        if method == "DELETE":
            self.events.pop(event_id, None)
            return httpx.Response(204)
        value = copy.deepcopy(kwargs["json"])
        value.setdefault("id", event_id)
        value["etag"] = str(self.writes)
        self.events[value["id"]] = value
        if self.lose_response:
            self.lose_response = False
            raise httpx.ReadTimeout("simulated lost response")
        return httpx.Response(200, json=value)


@pytest.fixture
def planned(session):
    profile = get_or_create_profile(session)
    row = PlannedAction(
        profile_id=profile.id,
        title="Work",
        description="Details",
        est_hours=2,
        week_of=datetime(2026, 10, 19).date(),
        starts_at=datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
        ends_at=datetime(2026, 10, 25, 1, 30, tzinfo=UTC),
    )
    session.add(row)
    session.commit()
    return row


def test_creation_retry_and_both_directions(session, planned):
    api = FakeGoogle(session)
    api.lose_response = True
    with pytest.raises(httpx.ReadTimeout):
        synchronize(api)
    event_id = planned.calendar_event_id
    assert len(api.events) == 1
    synchronize(api)
    assert planned.calendar_event_id == event_id and api.writes == 1
    planned.title = "Local change"
    session.commit()
    synchronize(api)
    assert api.events[event_id]["summary"] == "Local change"
    api.events[event_id]["summary"] = "Google change"
    api.events[event_id]["description"] = "Google note"
    api.events[event_id]["start"]["dateTime"] = "2026-10-26T10:00:00+01:00"
    api.events[event_id]["end"]["dateTime"] = "2026-10-26T11:00:00+01:00"
    synchronize(api)
    assert planned.title == "Google change" and planned.description == "Google note"
    assert str(planned.week_of) == "2026-10-26"


def test_conflict_resolution_and_stale_choice(session, planned):
    api = FakeGoogle(session)
    synchronize(api)
    planned.title = "Local"
    session.commit()
    api.events[planned.calendar_event_id]["summary"] = "Remote"
    assert synchronize(api)["conflicts"] == 1
    assert planned.title == "Local"
    api.events[planned.calendar_event_id]["summary"] = "Remote newer"
    with pytest.raises(HTTPException) as error:
        synchronize(api, (planned.id, "google"))
    assert error.value.status_code == 409
    synchronize(api, (planned.id, "google"))
    assert planned.title == "Remote newer" and planned.conflict is None


def test_deletion_only_unschedules_and_can_reschedule(session, planned):
    api = FakeGoogle(session)
    synchronize(api)
    planned.status = "done"
    session.commit()
    old_id = planned.calendar_event_id
    api.events.pop(old_id)
    synchronize(api)
    assert planned.starts_at is None and planned.status == "done"
    assert planned.title == "Work"
    planned.starts_at = datetime(2026, 11, 1, 12, tzinfo=UTC)
    planned.ends_at = datetime(2026, 11, 1, 13, tzinfo=UTC)
    session.commit()
    synchronize(api)
    assert planned.calendar_event_id != old_id and len(api.events) == 1


def test_event_ownership_and_cancel(session, planned):
    api = FakeGoogle(session)
    synchronize(api)
    event = api.events[planned.calendar_event_id]
    event["extendedProperties"] = {}
    with pytest.raises(HTTPException):
        synchronize(api)
    event["extendedProperties"] = {"private": {"growthos_plan": str(planned.id)}}
    planned.status = "cancelled"
    session.commit()
    synchronize(api)
    assert not api.events


def test_dpapi_roundtrip_and_no_plaintext():
    secret = {"access_token": "not-a-real-token", "refresh_token": "test-refresh"}
    protected = protect(secret)
    assert "not-a-real-token" not in protected
    assert reveal(protected) == secret


def test_status_excludes_tokens_and_disconnect(client, session):
    row = connection(session)
    row.protected_tokens = protect({"access_token": "test-secret"})
    session.commit()
    assert "test-secret" not in client.get("/calendar/status").text
    assert "protected_tokens" not in client.get("/calendar/status").text
    client.post("/calendar/disconnect")
    session.refresh(row)
    assert row.protected_tokens is None


def test_refresh_failure_and_missing_calendar(session):
    row = connection(session)
    row.calendar_id = "dedicated"
    row.protected_tokens = protect(
        {"access_token": "test", "expires_at": 0, "refresh_token": "test"}
    )
    session.commit()
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400))) as client,
        pytest.raises(HTTPException),
    ):
        GoogleCalendar(session, client).token()
    assert row.state == "reauthorize"
    row.protected_tokens = protect({"access_token": "test", "expires_at": time.time() + 1000})
    session.commit()
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as client,
        pytest.raises(HTTPException),
    ):
        GoogleCalendar(session, client).check()
    assert row.state == "calendar_missing"


def test_calendar_creation_is_not_repeated(session):
    row = connection(session)
    row.protected_tokens = protect({"access_token": "test", "expires_at": time.time() + 1000})
    session.commit()
    calls = []

    def request(req):
        calls.append(req.method)
        return httpx.Response(200, json={"id": "dedicated"})

    with httpx.Client(transport=httpx.MockTransport(request)) as client:
        api = GoogleCalendar(session, client)
        api.create()
        api.create()
    assert calls == ["POST", "GET"]


def test_prague_dst_absolute_duration(planned):
    value = remote_value(
        {
            "start": {"dateTime": "2026-10-25T02:30:00+02:00"},
            "end": {"dateTime": "2026-10-25T02:30:00+01:00"},
        }
    )
    apply_remote(planned, value)
    assert (planned.ends_at - planned.starts_at).total_seconds() == 3600
    assert local_value(planned)["starts_at"].endswith("+00:00")


def test_oauth_pkce_state_and_reconnect(session, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.calendar.google import SCOPE, begin, finish
    from app.config import Settings

    monkeypatch.setattr(
        "app.calendar.google.get_settings",
        lambda: Settings(google_client_id="test-client", google_client_secret="test-secret"),
    )
    url = begin(session)
    params = parse_qs(urlparse(url).query)
    assert params["scope"] == [SCOPE]
    assert params["code_challenge_method"] == ["S256"]
    row = connection(session)
    assert params["state"][0] not in row.protected_oauth

    def exchange(request):
        assert b"code_verifier=" in request.content
        return httpx.Response(
            200, json={"access_token": "test", "refresh_token": "refresh", "scope": SCOPE}
        )

    with httpx.Client(transport=httpx.MockTransport(exchange)) as client:
        with pytest.raises(HTTPException):
            finish(session, "bad-state", "code", client)
        finish(session, params["state"][0], "code", client)
        assert row.state == "needs_calendar" and row.protected_oauth is None
        with pytest.raises(HTTPException):
            finish(session, params["state"][0], "code", client)
    assert reveal(row.protected_tokens)["refresh_token"] == "refresh"


def test_pending_calendar_survives_reauthorization(session, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.calendar.google import SCOPE, begin, finish
    from app.config import Settings

    monkeypatch.setattr(
        "app.calendar.google.get_settings",
        lambda: Settings(google_client_id="test-client", google_client_secret="test-secret"),
    )
    row = connection(session)
    row.metadata_json = {"creation_pending": True, "marker": "our-marker"}
    session.commit()
    state = parse_qs(urlparse(begin(session)).query)["state"][0]
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"access_token": "test", "refresh_token": "refresh", "scope": SCOPE}
            )
        )
    ) as client:
        finish(session, state, "code", client)
    assert row.state == "creation_pending"


def test_missing_calendar_reset_preserves_plan(client, session, planned):
    row = connection(session)
    row.state, row.calendar_id = "calendar_missing", "deleted"
    planned.calendar_event_id = "old-event"
    session.commit()
    assert client.post("/calendar/replace-missing", json={"confirmed": False}).status_code == 422
    assert client.post("/calendar/replace-missing", json={"confirmed": True}).status_code == 200
    session.refresh(planned)
    assert planned.starts_at and planned.title == "Work" and planned.calendar_event_id is None


def test_retry_after_remote_delete_ack_is_lost(session, planned):
    api = FakeGoogle(session)
    synchronize(api)
    old_id = planned.calendar_event_id
    planned.starts_at = planned.ends_at = None
    session.commit()
    api.events.pop(old_id)
    synchronize(api)
    assert planned.calendar_event_id is None


def test_spring_dst(planned):
    value = remote_value(
        {
            "start": {"dateTime": "2026-03-29T01:30:00+01:00"},
            "end": {"dateTime": "2026-03-29T03:30:00+02:00"},
        }
    )
    apply_remote(planned, value)
    assert (planned.ends_at - planned.starts_at).total_seconds() == 3600
