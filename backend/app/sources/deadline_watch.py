"""Deadline watcher (ADR 0006): finds newly published deadlines on official pages.

For each open item with a ``watch_url`` the page is fetched and reduced to text. When the text
changed since the last check, an LLM proposes ``{deadline_date, quote}`` and code verifies it:

1. the quote appears verbatim (whitespace-normalized) in the page text,
2. the proposed date is written in that quote,
3. the date is in the future.

Only then is the deadline stored (as ``deadline_source="extracted"`` with the quote). Anything
else keeps the deadline unknown — the LLM never decides a deadline on its own.
"""

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import LLMProvider, ProviderError
from app.opportunities.models import Opportunity
from app.opportunities.service import EXTRACTED
from app.sources.curated import to_utc

logger = logging.getLogger("growthos.deadline_watch")

PROMPT_VERSION = "1"  # bump to re-check every page after changing the prompt/verification
MAX_LLM_CHARS = 12_000
MAX_QUOTE_CHARS = 400
MIN_PAGE_CHARS = 200  # less text = JS-rendered page; nothing to read, don't call the LLM

INSTRUCTIONS = """You read the text of an official web page of a competition, olympiad, programme
or event (mostly in Czech). Find the NEXT application / registration / submission deadline for the
UPCOMING edition. Return:
- deadline_date: that deadline as YYYY-MM-DD, or null if the page does not state it,
- quote: the exact sentence or line from the text that states the deadline, copied character for
  character (it must contain the date), or null,
- edition: the edition/year the deadline belongs to, if stated.
Ignore deadlines of past editions and dates that are not deadlines (event days, results).
If unsure, return nulls."""

MONTHS_CS = [
    "ledna|leden", "února|únor", "března|březen", "dubna|duben", "května|květen",
    "června|červen", "července|červenec", "srpna|srpen", "září", "října|říjen",
    "listopadu|listopad", "prosince|prosinec",
]  # fmt: skip
MONTHS_EN = [
    "january|jan", "february|feb", "march|mar", "april|apr", "may", "june|jun", "july|jul",
    "august|aug", "september|sept|sep", "october|oct", "november|nov", "december|dec",
]  # fmt: skip


class DeadlineExtraction(BaseModel):
    deadline_date: date | None = None
    quote: str | None = Field(default=None, max_length=2000)
    edition: str | None = None


class WatchReport(BaseModel):
    checked: int = 0
    unchanged: int = 0
    extracted: int = 0
    rejected: int = 0  # LLM answered but verification failed (or no deadline on the page)
    failed: int = 0  # page or LLM unreachable
    errors: list[str] = Field(default_factory=list)


# --- page text -------------------------------------------------------------------------

_BLOCK = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "section", "td", "th"}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript", "svg", "template"):
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "svg", "template"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text).replace(" ", " ")).strip()


def page_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    lines = (normalize(line) for line in "".join(parser.parts).split("\n"))
    return "\n".join(line for line in lines if line)


_DATEISH = re.compile(
    r"\d{1,2}\.\s*\d{1,2}\.|\b20\d\d\b|" + "|".join(MONTHS_CS + MONTHS_EN), re.IGNORECASE
)


def llm_excerpt(text: str) -> str:
    """Short pages go whole; long ones keep the lines that mention dates (plus neighbours)."""
    if len(text) <= MAX_LLM_CHARS:
        return text
    lines = text.split("\n")
    keep: set[int] = set()
    for i, line in enumerate(lines):
        if _DATEISH.search(line):
            keep.update({i - 1, i, i + 1})
    excerpt = "\n".join(lines[i] for i in sorted(keep) if 0 <= i < len(lines))
    return (excerpt or text)[:MAX_LLM_CHARS]


# --- verification ----------------------------------------------------------------------


def _date_patterns(value: date) -> list[re.Pattern[str]]:
    d, m, y = value.day, value.month, value.year
    day = rf"0?{d}"
    month = rf"0?{m}"
    return [
        re.compile(rf"(?<!\d){day}\.\s*{month}\."),  # 15. 11. / 15.11.2026
        re.compile(rf"(?<!\d){day}\.\s*(?:{MONTHS_CS[m - 1]})\b", re.IGNORECASE),
        re.compile(rf"(?<!\d){day}(?:st|nd|rd|th)?\s+(?:{MONTHS_EN[m - 1]})\b", re.IGNORECASE),
        re.compile(rf"\b(?:{MONTHS_EN[m - 1]})\.?\s+{day}(?:st|nd|rd|th)?\b", re.IGNORECASE),
        re.compile(rf"\b{y}-{m:02d}-{d:02d}\b"),
        re.compile(rf"(?<!\d){day}/{month}/{y}\b"),
    ]


def date_in_quote(value: date, quote: str) -> bool:
    if not any(p.search(quote) for p in _date_patterns(value)):
        return False
    years = {int(y) for y in re.findall(r"\b(20\d\d)\b", quote)}
    return not years or value.year in years


def verify(extraction: DeadlineExtraction, text: str, now: datetime) -> datetime | None:
    """The stored deadline, or None when the LLM claim is not backed by the page."""
    if extraction.deadline_date is None or not extraction.quote:
        return None
    quote = normalize(extraction.quote)
    if not quote or len(quote) > MAX_QUOTE_CHARS:
        return None
    if quote.casefold() not in normalize(text).casefold():
        return None  # not on the page → hallucinated or paraphrased
    if not date_in_quote(extraction.deadline_date, quote):
        return None
    deadline = to_utc(extraction.deadline_date)  # a bare date means 23:59 Prague
    if deadline <= now or deadline > now + timedelta(days=550):
        return None  # past, or implausibly far (e.g. a misread year)
    return deadline


# --- runner step -----------------------------------------------------------------------


def _hash(text: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\n{text}".encode()).hexdigest()


def _needs_watch(row: Opportunity, now: datetime) -> bool:
    has_source_deadline = (
        row.deadline_source == "source" and row.deadline_at is not None and row.deadline_at > now
    )
    return bool(row.watch_url) and not has_source_deadline


def watch_deadlines(
    session: Session, provider: LLMProvider, client: httpx.Client, now: datetime
) -> WatchReport:
    report = WatchReport()
    rows = session.scalars(
        select(Opportunity).where(Opportunity.status == "open", Opportunity.watch_url.is_not(None))
    ).all()
    for row in rows:
        if not _needs_watch(row, now):
            continue
        report.checked += 1
        try:
            response = client.get(row.watch_url)
            response.raise_for_status()
            text = page_text(response.text)
            digest = _hash(text)
            if digest == row.watch_hash:
                report.unchanged += 1
                continue
            if len(text) < MIN_PAGE_CHARS:
                report.failed += 1
                report.errors.append(f"{row.source_ref}: stránka nemá čitelný text (JS?)")
                continue
            extraction = provider.extract(llm_excerpt(text), DeadlineExtraction, INSTRUCTIONS)
        except (httpx.HTTPError, ProviderError) as exc:
            report.failed += 1
            report.errors.append(f"{row.source_ref}: {exc}"[:300])
            logger.warning("deadline watch %s failed: %s", row.source_ref, exc)
            continue  # hash untouched → retried next run; stored deadline untouched

        deadline = verify(extraction, text, now)
        row.watch_hash = digest
        row.deadline_checked_at = now
        if deadline is not None:
            row.deadline_at = deadline
            row.deadline_source = EXTRACTED
            row.deadline_quote = normalize(extraction.quote or "")
            report.extracted += 1
        else:
            report.rejected += 1
            stale = (
                row.deadline_source == EXTRACTED
                and row.deadline_quote
                and row.deadline_quote.casefold() not in normalize(text).casefold()
            )
            if stale:  # the page no longer says what we quoted → stop claiming it
                row.deadline_at = None
                row.deadline_source = None
                row.deadline_quote = None
        session.commit()
    return report
