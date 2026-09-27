"""Runs all enabled source adapters and syncs curated actions into the database."""

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.opportunities.service import UpsertResult, sync_actions, upsert_opportunities
from app.sources.base import SourceAdapter
from app.sources.curated import CuratedSource, load_curated_actions
from app.sources.devpost import DevpostSource
from app.sources.http import make_client
from app.sources.models import SourceRun

logger = logging.getLogger("growthos.sources")


class SourceReport(BaseModel):
    source: str
    status: str = "ok"  # ok | error | not_configured
    fetched: int = 0
    result: UpsertResult | None = None
    error: str | None = None


class RunReport(BaseModel):
    ran_at: datetime
    sources: list[SourceReport]
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
    return [CuratedSource(), DevpostSource(client)]


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


def run_sources(
    session: Session, now: datetime, adapters: list[SourceAdapter] | None = None
) -> RunReport:
    settings = get_settings()
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

    run = RunReport(ran_at=now, sources=reports)
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
    for adapter in all_adapters(settings, None):
        last = session.scalars(
            select(SourceRun)
            .where(SourceRun.source == adapter.id)
            .order_by(SourceRun.ran_at.desc())
            .limit(1)
        ).first()
        statuses.append(
            SourceStatus(
                id=adapter.id,
                name=adapter.name,
                enabled=adapter.id in settings.enabled_sources,
                configured=_is_configured(adapter),
                last_run=last.ran_at if last else None,
                last_status=last.status if last else None,
                last_error=last.error if last else None,
                last_fetched=last.fetched if last else None,
            )
        )
    return statuses
