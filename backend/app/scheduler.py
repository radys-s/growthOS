"""Weekly source refresh (in-process APScheduler, no Redis/Celery — ADR 0001)."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.common import utcnow
from app.db import SessionLocal
from app.sources.runner import run_sources

logger = logging.getLogger("growthos.scheduler")


def refresh_sources() -> None:
    with SessionLocal() as session:
        report = run_sources(session, utcnow())
    logger.info("sources refreshed: %s", report.model_dump_json())


def start_scheduler(run_now: bool = True) -> BackgroundScheduler:
    """Weekly refresh; ``run_now`` also refreshes once in the background right after startup,
    so slow network sources never block the API from starting."""
    scheduler = BackgroundScheduler(timezone="UTC")
    if run_now:
        scheduler.add_job(refresh_sources, id="refresh_sources_startup")
    scheduler.add_job(
        refresh_sources, "cron", day_of_week="mon", hour=5, id="refresh_sources", coalesce=True
    )
    scheduler.start()
    return scheduler
