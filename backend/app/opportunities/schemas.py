import uuid
from datetime import datetime

from pydantic import BaseModel

from app.opportunities.deadlines import DeadlineInfo
from app.sources.base import Eligibility


class OpportunityOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    organizer: str
    url: str
    description: str | None
    deadline: DeadlineInfo
    starts_at: datetime | None
    ends_at: datetime | None
    eligibility: Eligibility
    cost_eur: int | None
    location: str
    difficulty: int | None
    est_hours: int | None
    signals: list[str]
    cv_signal: int | None
    cv_signal_reason: str | None
    source: str
    evidence_url: str
    fetched_at: datetime
    first_seen_at: datetime
