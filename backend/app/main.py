from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __doc__ as app_doc
from app.config import get_settings
from app.db import check_database, engine

app = FastAPI(title="growthOS", description=app_doc, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        time=datetime.now(UTC),
    )
