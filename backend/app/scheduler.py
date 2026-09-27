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


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        refresh_sources, "cron", day_of_week="mon", hour=5, id="refresh_sources", coalesce=True
    )
    scheduler.start()
    return scheduler
