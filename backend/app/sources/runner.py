"""Runs all enabled source adapters and syncs curated actions into the database."""

import logging
import threading
from datetime import datetime

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import LLMProvider, get_provider
from app.config import Settings, get_settings
from app.gmail.client import GmailClient
from app.gmail.client import connection as gmail_connection
from app.gmail.extract import GmailReport, process_gmail
from app.google import oauth
from app.opportunities.service import UpsertResult, sync_actions, upsert_opportunities
from app.sources.base import SourceAdapter
from app.sources.curated import CuratedSource, load_curated_actions
from app.sources.deadline_watch import WatchReport, watch_deadlines
from app.sources.devpost import DevpostSource
from app.sources.http import make_client
from app.sources.kaggle import KaggleSource
from app.sources.models import SourceRun

logger = logging.getLogger("growthos.sources")

WATCH_ID = "deadline_watch"
WATCH_NAME = "Hlídač deadlinů (LLM + ověřená citace)"
GMAIL_ID = "gmail"
GMAIL_NAME = "Gmail (jen zprávy se štítkem, LLM + ověřená citace)"
_DEFAULT = object()
# The startup/weekly job and POST /sources/run may overlap; two concurrent snapshots of the same
# source would race on inserts (unique dedup_key), so runs are serialized in-process.
_RUN_LOCK = threading.Lock()


class SourceReport(BaseModel):
    source: str
    status: str = "ok"  # ok | error | not_configured
    fetched: int = 0
    result: UpsertResult | None = None
    error: str | None = None


class RunReport(BaseModel):
    ran_at: datetime
    sources: list[SourceReport]
    deadline_watch: WatchReport | None = None
    gmail: GmailReport | None = None
    actions: int | None = None
    actions_error: str | None = None


class SourceStatus(BaseModel):
    id: str
    name: str
    enabled: bool
    configured: bool
    last_run: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    last_fetched: int | None = None


def all_adapters(settings: Settings, client: httpx.Client | None) -> list[SourceAdapter]:
    """Every known adapter, enabled or not. ``client`` is None when only listing them."""
    return [
        CuratedSource(),
        DevpostSource(client),
        KaggleSource(client, settings.kaggle_username, settings.kaggle_key),
    ]


def default_adapters(settings: Settings, client: httpx.Client) -> list[SourceAdapter]:
    enabled = settings.enabled_sources
    return [a for a in all_adapters(settings, client) if a.id in enabled]


def _is_configured(adapter: SourceAdapter) -> bool:
    return bool(getattr(adapter, "configured", True))


def _record(session: Session, report: SourceReport, now: datetime) -> None:
    result = report.result or UpsertResult()
    session.add(
        SourceRun(
            source=report.source,
            ran_at=now,
            status=report.status,
            fetched=report.fetched,
            created=result.created,
            updated=result.updated,
            closed=result.closed,
            error=report.error,
        )
    )
    session.commit()


def _run_watch(
    session: Session, provider: LLMProvider | None, client: httpx.Client, now: datetime
) -> tuple[SourceReport, WatchReport | None]:
    report = SourceReport(source=WATCH_ID)
    if provider is None:
        report.status = "not_configured"
        return report, None
    try:
        watch = watch_deadlines(session, provider, client, now)
    except Exception as exc:
        session.rollback()
        logger.exception("deadline watch failed")
        report.status = "error"
        report.error = str(exc)[:500]
        return report, None
    report.fetched = watch.checked
    report.result = UpsertResult(updated=watch.extracted, unchanged=watch.unchanged)
    if watch.errors:
        report.error = "; ".join(watch.errors)[:500]
    return report, watch


def _gmail_ready(session: Session, settings: Settings) -> bool:
    return oauth.configured(settings) and gmail_connection(session).state == "connected"


def _run_gmail(
    session: Session, provider: LLMProvider | None, client: httpx.Client, now: datetime
) -> tuple[SourceReport, GmailReport | None]:
    """Labelled mail only (ADR 0009); without a connection or an LLM nothing is read."""
    settings = get_settings()
    report = SourceReport(source=GMAIL_ID)
    if provider is None or not _gmail_ready(session, settings):
        report.status = "not_configured"
        return report, None
    try:
        gmail = process_gmail(session, provider, GmailClient(session, client), settings, now)
    except Exception as exc:
        session.rollback()
        logger.exception("gmail step failed")
        report.status = "error"
        report.error = str(getattr(exc, "detail", exc))[:500]
        return report, None
    report.fetched = gmail.checked
    report.result = UpsertResult(created=gmail.opportunities, updated=gmail.deadlines)
    if gmail.errors:
        report.error = "; ".join(gmail.errors)[:500]
    return report, gmail


def run_gmail(session: Session, now: datetime) -> SourceReport:
    """Only the Gmail step (the Gmail tab's "read now"); serialized with full runs."""
    with _RUN_LOCK, make_client() as client:
        report, _ = _run_gmail(session, get_provider(get_settings(), client), client, now)
        _record(session, report, now)
        return report


def run_sources(
    session: Session,
    now: datetime,
    adapters: list[SourceAdapter] | None = None,
    provider: LLMProvider | None | object = _DEFAULT,
) -> RunReport:
    """Fetch every source, then let the deadline watcher enrich items (ADR 0006).
    ``adapters``/``provider`` override the configured ones (tests)."""
    with _RUN_LOCK:
        return _run_sources(session, now, adapters, provider)


def _run_sources(
    session: Session,
    now: datetime,
    adapters: list[SourceAdapter] | None,
    provider: LLMProvider | None | object,
) -> RunReport:
    settings = get_settings()
    watch: WatchReport | None = None
    with make_client() as client:
        selected = adapters if adapters is not None else default_adapters(settings, client)
        reports: list[SourceReport] = []
        for adapter in selected:
            report = SourceReport(source=adapter.id)
            if not _is_configured(adapter):
                report.status = "not_configured"
            else:
                try:
                    items = adapter.fetch(now)
                    report.fetched = len(items)
                    report.result = upsert_opportunities(session, adapter.id, items)
                except Exception as exc:  # one broken source must not stop the others
                    session.rollback()
                    logger.exception("source %s failed", adapter.id)
                    report.status = "error"
                    report.error = str(exc)[:500]
            _record(session, report, now)
            reports.append(report)

        llm = get_provider(settings, client) if provider is _DEFAULT else provider
        watch_report, watch = _run_watch(session, llm, client, now)  # type: ignore[arg-type]
        _record(session, watch_report, now)
        reports.append(watch_report)

        gmail: GmailReport | None = None
        if GMAIL_ID in settings.enabled_sources:
            gmail_report, gmail = _run_gmail(session, llm, client, now)  # type: ignore[arg-type]
            _record(session, gmail_report, now)
            reports.append(gmail_report)

    run = RunReport(ran_at=now, sources=reports, deadline_watch=watch, gmail=gmail)
    try:
        run.actions = sync_actions(session, load_curated_actions())
    except Exception as exc:
        session.rollback()
        logger.exception("curated actions failed")
        run.actions_error = str(exc)
    return run


def source_statuses(session: Session) -> list[SourceStatus]:
    settings = get_settings()
    statuses: list[SourceStatus] = []
    entries = [
        (a.id, a.name, a.id in settings.enabled_sources, _is_configured(a))
        for a in all_adapters(settings, None)
    ]
    llm = bool(settings.llm_base_url.strip())
    entries.append((WATCH_ID, WATCH_NAME, True, llm))
    entries.append(
        (
            GMAIL_ID,
            GMAIL_NAME,
            GMAIL_ID in settings.enabled_sources,
            llm and _gmail_ready(session, settings),
        )
    )
    for source_id, name, enabled, configured in entries:
        last = session.scalars(
            select(SourceRun)
            .where(SourceRun.source == source_id)
            .order_by(SourceRun.ran_at.desc())
            .limit(1)
        ).first()
        statuses.append(
            SourceStatus(
                id=source_id,
                name=name,
                enabled=enabled,
                configured=configured,
                last_run=last.ran_at if last else None,
                last_status=last.status if last else None,
                last_error=last.error if last else None,
                last_fetched=last.fetched if last else None,
            )
        )
    return statuses
