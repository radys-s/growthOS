import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TargetType(StrEnum):
    OPPORTUNITY = "opportunity"
    ACTION = "action"


class DecisionStatus(StrEnum):
    REVERSED = "reversed"
    USEFUL = "useful"
    PLANNED = "planned"  # stays in the list, marked as planned
    DONE = "done"  # hidden
    SKIPPED = "skipped"  # hidden
    NOT_INTERESTED = "not_interested"  # hidden
    ALREADY_KNEW = "already_knew"  # stays visible, does not count as "new to me"


class DecisionIn(BaseModel):
    target_type: TargetType
    target_id: uuid.UUID
    status: DecisionStatus
    note: str | None = Field(default=None, max_length=2000)


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    status: str
    note: str | None
    created_at: datetime
