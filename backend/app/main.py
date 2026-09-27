import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __doc__ as app_doc
from app.common import utcnow
from app.config import get_settings
from app.db import check_database, engine
from app.decisions.router import router as decisions_router
from app.goals.router import router as goals_router
from app.opportunities.router import router as opportunities_router
from app.profile.router import router as profile_router
from app.recommendations.router import router as recommendations_router
from app.scheduler import refresh_sources, start_scheduler
from app.seed import run as run_seed

logger = logging.getLogger("growthos")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Create the single profile + goals once at startup, so parallel first requests
    # never race each other into creating duplicate profiles.
    try:
        logger.info("seed: %s", run_seed())
    except Exception:
        logger.exception("startup seed failed (is the database migrated?)")
    scheduler = None
    if get_settings().scheduler_enabled:
        try:
            refresh_sources()
        except Exception:
            logger.exception("startup source refresh failed")
        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="growthOS", description=app_doc, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile_router)
app.include_router(goals_router)
app.include_router(opportunities_router)
app.include_router(recommendations_router)
app.include_router(decisions_router)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unreachable"]
    database_dialect: str
    time: datetime


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_ok = check_database()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="ok" if db_ok else "unreachable",
        database_dialect=engine.dialect.name,
        time=utcnow(),
    )
