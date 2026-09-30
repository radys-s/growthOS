"""Read-only Gmail access: only messages with the user's chosen label are ever listed (ADR 0009).

Attachments are never downloaded; bodies stay in memory and are capped before they reach the LLM.
"""

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.gmail.models import GmailConnection
from app.google import oauth
from app.sources.deadline_watch import llm_excerpt, normalize, page_text

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
API = "https://gmail.googleapis.com/gmail/v1/users/me/"
MAX_AGE_QUERY = "newer_than:365d"


@dataclass
class MailMessage:
    id: str
    subject: str
    sent_at: datetime | None
    text: str  # normalized plain text, capped for the LLM

    @property
    def permalink(self) -> str:
        return "https://mail.google.com/mail/u/0/#all/" + self.id


def connection(session: Session) -> GmailConnection:
    return oauth.single_row(session, GmailConnection)


def _decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except (binascii.Error, ValueError):
        return ""


def _parts(payload: dict) -> list[dict]:
    """Depth-first leaves of the MIME tree, without attachments (parts with a filename)."""
    if payload.get("filename"):
        return []
    children = payload.get("parts") or []
    if not children:
        return [payload]
    return [leaf for child in children for leaf in _parts(child)]


def body_text(payload: dict) -> str:
    leaves = _parts(payload)
    for mime, convert in (("text/plain", normalize_lines), ("text/html", page_text)):
        chunks = [
            _decode(p.get("body", {}).get("data", ""))
            for p in leaves
            if p.get("mimeType") == mime and p.get("body", {}).get("data")
        ]
        text = convert("\n".join(chunks))
        if text:
            return text
    return ""


def normalize_lines(text: str) -> str:
    lines = (normalize(line) for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def _header(payload: dict, name: str) -> str:
    for header in payload.get("headers", []):
        if header.get("name", "").lower() == name:
            return header.get("value", "")
    return ""


class GmailClient:
    def __init__(self, session: Session, client: httpx.Client):
        self.session, self.client = session, client
        self.row = connection(session)

    def get(self, path: str, **params) -> dict:
        token = oauth.access_token(self.session, self.row, get_settings(), self.client)
        response = self.client.get(
            API + path, params=params, headers={"Authorization": "Bearer " + token}
        )
        oauth.checked(self.session, self.row, response)
        if response.status_code != 200:
            raise HTTPException(502, f"Gmail vrátil neočekávanou odpověď ({response.status_code}).")
        return response.json()

    def label_id(self, name: str) -> str | None:
        for label in self.get("labels").get("labels", []):
            if label.get("name", "").casefold() == name.casefold():
                return label["id"]
        return None

    def message_ids(self, label_id: str, limit: int) -> list[str]:
        """Newest labelled messages first; the label filter is applied by Gmail itself."""
        data = self.get(
            "messages", labelIds=label_id, q=MAX_AGE_QUERY, maxResults=max(1, min(limit, 500))
        )
        return [m["id"] for m in data.get("messages", [])]

    def message(self, message_id: str) -> MailMessage:
        data = self.get("messages/" + message_id, format="full")
        payload = data.get("payload", {})
        sent_at = None
        if str(data.get("internalDate", "")).isdigit():
            sent_at = datetime.fromtimestamp(int(data["internalDate"]) / 1000, UTC)
        subject = normalize(_header(payload, "subject"))
        body = body_text(payload)
        text = (f"Subject: {subject}\n" if subject else "") + body
        return MailMessage(message_id, subject, sent_at, llm_excerpt(text))
