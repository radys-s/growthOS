"""Gmail step (ADR 0009): labelled mail → LLM proposals → deterministic verification.

The LLM only proposes. Code keeps a claim only when its quote appears verbatim in the message;
a deadline or date only when it is written in that quote; an organizer, URL or result only when
it appears in the message. Anything else is dropped (field → null, or the whole item).
Opportunities are stored as unverified; achievements become import proposals the user confirms.
"""

import logging
from datetime import date, datetime

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import LLMProvider, ProviderError
from app.config import Settings
from app.gmail.client import GmailClient, MailMessage
from app.gmail.models import GmailMessage
from app.growth.imports import propose_extracted
from app.growth.locking import WRITE_LOCK
from app.opportunities.models import Opportunity
from app.opportunities.service import EXTRACTED, add_extracted_opportunity
from app.profile.service import get_or_create_profile
from app.sources.base import NormalizedOpportunity, OpportunityKind
from app.sources.curated import PRAGUE, to_utc
from app.sources.deadline_watch import (
    MAX_QUOTE_CHARS,
    DeadlineExtraction,
    date_in_quote,
    normalize,
    verify,
)

logger = logging.getLogger("growthos.gmail")

SOURCE = "gmail"
MIN_TEXT_CHARS = 40  # shorter = nothing worth sending to the LLM
UNKNOWN_ORGANIZER = "Neuvedeno (Gmail)"

INSTRUCTIONS = f"""You read one e-mail (mostly Czech or English) that the user labelled as relevant
to their career growth. Extract only what the e-mail itself states:
- opportunities: competitions, olympiads, hackathons, internships, scholarships, programmes,
  summer schools or certifications the reader can still apply to. For each: title, kind (one of
  {", ".join(k.value for k in OpportunityKind)}), organizer (as written), url (the link to the
  opportunity, copied exactly, or null), deadline_date (YYYY-MM-DD application deadline, or null)
  and quote: the exact sentence from the e-mail that mentions it (with the deadline, if any).
- achievements: results the reader already achieved (award, placement, accepted application,
  completed certificate). For each: title, result (e.g. "2. místo", as written, or null),
  achieved_on (YYYY-MM-DD, or null) and quote: the exact sentence stating it.
Quotes must be copied character for character from the e-mail and be at most one or two
sentences. Newsletters, ads and generic tips are not opportunities unless they name a concrete
one. If unsure, leave the item out. Return empty lists when there is nothing."""


class MailOpportunity(BaseModel):
    title: str | None = None
    kind: str | None = None
    organizer: str | None = None
    url: str | None = None
    deadline_date: date | None = None
    quote: str | None = Field(default=None, max_length=2000)


class MailAchievement(BaseModel):
    title: str | None = None
    result: str | None = None
    achieved_on: date | None = None
    quote: str | None = Field(default=None, max_length=2000)


class MailExtraction(BaseModel):
    opportunities: list[MailOpportunity] = Field(default_factory=list, max_length=20)
    achievements: list[MailAchievement] = Field(default_factory=list, max_length=20)


class GmailReport(BaseModel):
    listed: int = 0  # labelled messages returned by Gmail (newest first, capped)
    checked: int = 0  # new messages read this run
    opportunities: int = 0  # new opportunities stored
    deadlines: int = 0  # deadlines filled in on already known opportunities
    proposals: int = 0  # new achievement proposals waiting for confirmation
    rejected: int = 0  # LLM claims dropped by verification
    failed: int = 0  # message or LLM unreachable → retried next run
    errors: list[str] = Field(default_factory=list)


def _in_text(value: str, text: str) -> bool:
    value = normalize(value).casefold()
    return bool(value) and value in normalize(text).casefold()


def verified_quote(quote: str | None, text: str) -> str | None:
    value = normalize(quote or "")
    if not value or len(value) > MAX_QUOTE_CHARS or not _in_text(value, text):
        return None
    return value


def _url(value: str | None, text: str) -> str | None:
    value = (value or "").strip()
    if not value.startswith(("https://", "http://")):
        return None
    for candidate in (value, value.rstrip("/")):
        if candidate in text:
            return candidate
    return None


def check_opportunity(
    claim: MailOpportunity, message: MailMessage, n: int, now: datetime
) -> tuple[NormalizedOpportunity, str] | None:
    """A verified opportunity plus its quote, or None when the claim is not backed by the mail."""
    text = message.text
    quote = verified_quote(claim.quote, text)
    title = normalize(claim.title or "")[:300]
    if quote is None or not title or claim.kind not in set(OpportunityKind):
        return None
    deadline = None
    if claim.deadline_date is not None:
        deadline = verify(
            DeadlineExtraction(deadline_date=claim.deadline_date, quote=quote), text, now
        )
        passed = to_utc(claim.deadline_date) <= now
        if deadline is None and passed and date_in_quote(claim.deadline_date, quote):
            return None  # the mail's own deadline has passed: nothing to apply to
    organizer = normalize(claim.organizer or "")[:200]
    try:
        item = NormalizedOpportunity(
            kind=OpportunityKind(claim.kind),
            title=title,
            organizer=organizer if _in_text(organizer, text) else UNKNOWN_ORGANIZER,
            url=_url(claim.url, text) or message.permalink,
            description=quote,
            deadline_at=deadline,
            location="neuvedeno",
            source=SOURCE,
            source_ref=f"{message.id}:{n}",
            evidence_url=message.permalink,
            fetched_at=now,
        )
    except ValidationError:
        return None
    return item, quote


def check_achievement(claim: MailAchievement, message: MailMessage) -> dict | None:
    quote = verified_quote(claim.quote, message.text)
    title = normalize(claim.title or "")[:300]
    if quote is None or not title:
        return None
    result = normalize(claim.result or "")[:200]
    achieved = claim.achieved_on
    today = datetime.now(PRAGUE).date()
    if achieved is not None and (achieved > today or not date_in_quote(achieved, quote)):
        achieved = None
    return {
        "title": title,
        "description": quote,
        "result": result if _in_text(result, message.text) else None,
        "achieved_on": achieved.isoformat() if achieved else None,
    }


def _known(session: Session, url: str) -> Opportunity | None:
    """An open opportunity from another source with this URL (tolerating a trailing slash)."""
    return session.scalars(
        select(Opportunity).where(
            Opportunity.status == "open",
            Opportunity.source != SOURCE,
            Opportunity.url.in_({url, url.rstrip("/"), url.rstrip("/") + "/"}),
        )
    ).first()


def store(
    session: Session, message: MailMessage, extraction: MailExtraction, now: datetime
) -> GmailReport:
    """Verify and persist one message's claims; marks the message as processed."""
    report = GmailReport()
    profile = get_or_create_profile(session)
    found = 0
    for n, claim in enumerate(extraction.opportunities):
        checked = check_opportunity(claim, message, n, now)
        if checked is None:
            report.rejected += 1
            continue
        item, quote = checked
        found += 1
        known = _known(session, str(item.url)) if str(item.url) != message.permalink else None
        if known is not None:
            if known.deadline_at is None and item.deadline_at is not None:
                known.deadline_at = item.deadline_at
                known.deadline_source = EXTRACTED
                known.deadline_quote = quote
                report.deadlines += 1
            continue
        if add_extracted_opportunity(session, SOURCE, item, quote):
            report.opportunities += 1
    for claim in extraction.achievements:
        proposed = check_achievement(claim, message)
        if proposed is None:
            report.rejected += 1
            continue
        found += 1
        if propose_extracted(
            session,
            profile,
            SOURCE,
            message.id,
            message.permalink,
            proposed["description"],
            proposed,
        ):
            report.proposals += 1
    session.add(GmailMessage(message_id=message.id, processed_at=now, status="ok", found=found))
    session.commit()
    return report


def _add(total: GmailReport, part: GmailReport) -> None:
    for key in ("opportunities", "deadlines", "proposals", "rejected"):
        setattr(total, key, getattr(total, key) + getattr(part, key))


def process_gmail(
    session: Session, provider: LLMProvider, gmail: GmailClient, settings: Settings, now: datetime
) -> GmailReport:
    report = GmailReport()
    label = gmail.label_id(settings.gmail_label)
    if label is None:
        raise HTTPException(409, f"Štítek „{settings.gmail_label}“ v Gmailu neexistuje.")
    ids = gmail.message_ids(label, settings.gmail_max_messages)
    report.listed = len(ids)
    done = set(
        session.scalars(select(GmailMessage.message_id).where(GmailMessage.message_id.in_(ids)))
    )
    for message_id in ids:
        if message_id in done:
            continue
        report.checked += 1
        try:
            message = gmail.message(message_id)
            if len(message.text) < MIN_TEXT_CHARS:
                with WRITE_LOCK:
                    session.add(
                        GmailMessage(message_id=message_id, processed_at=now, status="empty")
                    )
                    session.commit()
                continue
            extraction = provider.extract(message.text, MailExtraction, INSTRUCTIONS)
        except HTTPException as exc:
            if exc.status_code == 409:  # access revoked: stop, the connection needs the user
                raise
            report.failed += 1
            report.errors.append(f"{message_id}: {exc.detail}"[:300])
            continue
        except (httpx.HTTPError, ProviderError) as exc:
            report.failed += 1
            report.errors.append(f"{message_id}: {exc}"[:300])
            logger.warning("gmail message %s failed: %s", message_id, exc)
            continue  # not marked → retried next run
        with WRITE_LOCK:
            _add(report, store(session, message, extraction, now))
    return report
