"""Honest deadline interpretation (ADR 0005): official vs expected vs unknown, never invented."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.sources.base import Recurrence

# Labels are human text for a Czech user; `date` stays UTC and the frontend localizes it.
LABEL_TZ = ZoneInfo("Europe/Prague")

MONTHS_CS = [
    "leden", "únor", "březen", "duben", "květen", "červen",
    "červenec", "srpen", "září", "říjen", "listopad", "prosinec",
]  # fmt: skip


class DeadlineKind(StrEnum):
    OFFICIAL = "official"  # published for the upcoming edition
    EXPECTED = "expected"  # projected from the previous edition, not published yet
    ROLLING = "rolling"  # continuous / monthly
    PASSED = "passed"  # official deadline passed, not recurring
    UNKNOWN = "unknown"  # not published, no history


class DeadlineInfo(BaseModel):
    kind: DeadlineKind
    date: datetime | None
    label: str
    # Set only for an official deadline found by the deadline watcher (ADR 0006):
    # the verbatim sentence from the official page and that page's URL.
    quote: str | None = None
    quote_url: str | None = None


def _add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 February
        return value.replace(year=value.year + years, day=28)


def project_next(last: datetime, now: datetime) -> datetime:
    """Move a past yearly deadline forward by whole years until it is in the future."""
    years = 0
    candidate = last
    while candidate <= now:
        years += 1
        candidate = _add_years(last, years)
    return candidate


def _day_label(value: datetime) -> str:
    local = value.astimezone(LABEL_TZ)
    return f"do {local.day}. {local.month}. {local.year}"


def deadline_info(
    deadline_at: datetime | None,
    recurrence: str | None,
    last_known_deadline: datetime | None,
    now: datetime,
) -> DeadlineInfo:
    if deadline_at is not None and deadline_at > now:
        return DeadlineInfo(
            kind=DeadlineKind.OFFICIAL,
            date=deadline_at,
            label=_day_label(deadline_at),
        )
    if recurrence == Recurrence.ROLLING:
        return DeadlineInfo(kind=DeadlineKind.ROLLING, date=None, label="průběžně")
    history = deadline_at or last_known_deadline
    if recurrence == Recurrence.YEARLY and history is not None:
        expected = project_next(history, now)
        local = expected.astimezone(LABEL_TZ)
        return DeadlineInfo(
            kind=DeadlineKind.EXPECTED,
            date=expected,
            label=f"očekáváno ~{MONTHS_CS[local.month - 1]} {local.year} (zatím nezveřejněno)",
        )
    if deadline_at is not None:
        return DeadlineInfo(kind=DeadlineKind.PASSED, date=deadline_at, label="deadline uplynul")
    if recurrence == Recurrence.YEARLY:
        return DeadlineInfo(
            kind=DeadlineKind.UNKNOWN, date=None, label="každoročně, termín zatím nezveřejněn"
        )
    return DeadlineInfo(kind=DeadlineKind.UNKNOWN, date=None, label="deadline nezveřejněn")


class _DeadlineRow(Protocol):
    deadline_at: datetime | None
    recurrence: str | None
    last_known_deadline: datetime | None
    deadline_source: str | None
    deadline_quote: str | None
    watch_url: str | None


def opportunity_deadline(row: _DeadlineRow, now: datetime) -> DeadlineInfo:
    info = deadline_info(row.deadline_at, row.recurrence, row.last_known_deadline, now)
    if info.kind == DeadlineKind.OFFICIAL and row.deadline_source == "extracted":
        info.quote = row.deadline_quote
        info.quote_url = row.watch_url
    return info
