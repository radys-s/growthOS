import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __doc__ as app_doc
from app.calendar.router import router as calendar_router
from app.common import utcnow
from app.config import get_settings
from app.db import check_database, engine
from app.decisions.router import router as decisions_router
from app.gmail.router import router as gmail_router
from app.goals.router import router as goals_router
from app.growth.router import router as growth_router
from app.opportunities.router import router as opportunities_router
from app.profile.router import router as profile_router
from app.recommendations.router import router as recommendations_router
from app.scheduler import start_scheduler
from app.seed import run as run_seed

logger = logging.getLogger("growthos")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Create the single profile + goals once at startup, so parallel first requests
    # never race each other into creating duplicate profiles.
    try:
        logger.info("seed: %s", run_seed())
    except Exception:
        logger.error("startup seed failed; check database migrations")
        raise
    scheduler = None
    if get_settings().scheduler_enabled:
        scheduler = start_scheduler(run_now=True)
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="growthOS", description=app_doc, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(calendar_router)
app.include_router(gmail_router)
app.include_router(growth_router)
app.include_router(profile_router)
app.include_router(goals_router)
app.include_router(opportunities_router)
app.include_router(recommendations_router)
app.include_router(decisions_router)


class HealthResponse(BaseModel):
    version: str = "0.2.0"
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


# Local single-user service: reject browser writes from untrusted origins, including multipart.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])


@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and origin
        and origin not in get_settings().cors_origin_list
    ):
        return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    return await call_next(request)
