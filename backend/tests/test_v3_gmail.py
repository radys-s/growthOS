import base64
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

from app.calendar.vault import protect, reveal
from app.config import Settings
from app.gmail.client import SCOPE, GmailClient, body_text, connection
from app.google import oauth

LABEL = {"id": "L1", "name": "growthOS"}


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def part(mime: str, text: str, filename: str = "") -> dict:
    return {"mimeType": mime, "filename": filename, "body": {"data": b64(text)}}


def connected(session):
    row = connection(session)
    row.protected_tokens = protect({"access_token": "tok", "expires_at": time.time() + 1000})
    row.state = "connected"
    session.commit()
    return row


def test_body_prefers_plain_text_and_skips_attachments():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    part("text/plain", "Uzávěrka   přihlášek\n\n30. 11. 2026"),
                    part("text/html", "<p>HTML verze</p>"),
                ],
            },
            part("text/plain", "SECRET ATTACHMENT", filename="cv.txt"),
        ],
    }
    assert body_text(payload) == "Uzávěrka přihlášek\n30. 11. 2026"


def test_body_falls_back_to_html():
    payload = {"mimeType": "text/html", "body": {"data": b64("<h1>Výzva</h1><p>Přihlas se</p>")}}
    assert body_text(payload) == "Výzva\nPřihlas se"


def test_client_reads_only_the_label(session):
    connected(session)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer tok"
        path = request.url.path
        if path.endswith("/labels"):
            return httpx.Response(
                200,
                json={
                    "labels": [{"id": "INBOX", "name": "INBOX"}, {"id": "L1", "name": "growthOS"}]
                },
            )
        if path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        return httpx.Response(
            200,
            json={
                "id": "m1",
                "internalDate": "1790000000000",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Subject", "value": "Hackathon  pozvánka"}],
                    "body": {"data": b64("Registrace do 1. 12. 2026")},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        gmail = GmailClient(session, http)
        assert gmail.label_id("GROWTHOS") == "L1"
        assert gmail.label_id("missing") is None
        assert gmail.message_ids("L1", 50) == ["m1"]
        message = gmail.message("m1")
    listing = parse_qs(urlparse(str(seen[2].url)).query)
    assert listing["labelIds"] == ["L1"] and listing["q"] == ["newer_than:365d"]
    assert message.text == "Subject: Hackathon pozvánka\nRegistrace do 1. 12. 2026"
    assert message.sent_at is not None and message.permalink.endswith("#all/m1")


def test_revoked_access_asks_to_reconnect(session):
    row = connected(session)

    def handler(request):
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http, pytest.raises(HTTPException) as err:
        GmailClient(session, http).label_id("growthOS")
    assert err.value.status_code == 409 and row.state == "reauthorize"


def test_rate_limit_is_transient(session):
    row = connected(session)

    def handler(request):
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http, pytest.raises(HTTPException) as err:
        GmailClient(session, http).label_id("growthOS")
    assert err.value.status_code == 503 and row.state == "connected"


def test_separate_readonly_grant(session):
    settings = Settings(google_client_id="c", google_client_secret="s")
    row = connection(session)
    url = oauth.begin(session, row, settings, SCOPE, settings.google_gmail_redirect_uri)
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == [SCOPE]
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/gmail/callback"]
    state = query["state"][0]

    def handler(request):
        return httpx.Response(
            200,
            json={"access_token": "a", "refresh_token": "r", "scope": SCOPE, "expires_in": 3600},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        oauth.finish(
            session, row, settings, SCOPE, settings.google_gmail_redirect_uri, state, "code", http
        )
    assert reveal(row.protected_tokens)["refresh_token"] == "r"


def test_grant_without_gmail_scope_is_rejected(session):
    settings = Settings(google_client_id="c", google_client_secret="s")
    row = connection(session)
    url = oauth.begin(session, row, settings, SCOPE, settings.google_gmail_redirect_uri)
    state = parse_qs(urlparse(url).query)["state"][0]

    def handler(request):
        return httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r", "scope": "openid"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http, pytest.raises(HTTPException):
        oauth.finish(
            session, row, settings, SCOPE, settings.google_gmail_redirect_uri, state, "code", http
        )
    assert row.protected_tokens is None


def test_status_and_disconnect(client, session):
    connected(session)
    body = client.get("/gmail/status").json()
    assert body["state"] == "connected" and body["label"] == "growthOS"
    assert body["llm_configured"] is False and body["processed"] == 0
    body = client.post("/gmail/disconnect").json()
    assert body["state"] == "disconnected"
