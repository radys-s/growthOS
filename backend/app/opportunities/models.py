import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common import utcnow
from app.db import Base, UTCDateTime


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("source", "source_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    organizer: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    recurrence: Mapped[str | None] = mapped_column(String(20))
    last_known_deadline: Mapped[datetime | None] = mapped_column(UTCDateTime)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    eligibility: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cost_eur: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[int | None] = mapped_column(Integer)
    est_hours: Mapped[int | None] = mapped_column(Integer)
    signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    cv_signal: Mapped[int | None] = mapped_column(Integer)
    cv_signal_reason: Mapped[str | None] = mapped_column(Text)
    credential_type: Mapped[str | None] = mapped_column(String(30))
    issuer_reputation: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50))
    source_ref: Mapped[str] = mapped_column(String(200))
    evidence_url: Mapped[str] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # Deadline watcher (ADR 0006): deadline_source is "source" or "extracted" (LLM + verified quote)
    watch_url: Mapped[str | None] = mapped_column(String(500))
    deadline_source: Mapped[str | None] = mapped_column(String(20))
    deadline_quote: Mapped[str | None] = mapped_column(Text)
    deadline_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    watch_hash: Mapped[str | None] = mapped_column(String(64))
    dedup_key: Mapped[str] = mapped_column(String(600), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="open")
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class GrowthAction(Base):
    __tablename__ = "growth_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_ref: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    est_hours: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[int | None] = mapped_column(Integer)
    cv_signal: Mapped[int | None] = mapped_column(Integer)
    cv_signal_reason: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
