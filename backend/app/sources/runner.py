"""Runs all enabled source adapters and syncs curated actions into the database."""

import logging
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.opportunities.service import UpsertResult, sync_actions, upsert_opportunities
from app.sources.base import SourceAdapter
from app.sources.curated import CuratedSource, load_curated_actions

logger = logging.getLogger("growthos.sources")


class SourceReport(BaseModel):
    source: str
    fetched: int = 0
    result: UpsertResult | None = None
    error: str | None = None


class RunReport(BaseModel):
    ran_at: datetime
    sources: list[SourceReport]
    actions: int | None = None
    actions_error: str | None = None


def default_adapters() -> list[SourceAdapter]:
    return [CuratedSource()]


def run_sources(
    session: Session, now: datetime, adapters: list[SourceAdapter] | None = None
) -> RunReport:
    reports: list[SourceReport] = []
    for adapter in adapters if adapters is not None else default_adapters():
        report = SourceReport(source=adapter.id)
        try:
            items = adapter.fetch(now)
            report.fetched = len(items)
            report.result = upsert_opportunities(session, adapter.id, items)
        except Exception as exc:  # one broken source must not stop the others
            session.rollback()
            logger.exception("source %s failed", adapter.id)
            report.error = str(exc)
        reports.append(report)

    run = RunReport(ran_at=now, sources=reports)
    try:
        run.actions = sync_actions(session, load_curated_actions())
    except Exception as exc:
        session.rollback()
        logger.exception("curated actions failed")
        run.actions_error = str(exc)
    return run
