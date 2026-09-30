import uuid
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.profile.schemas import ProfileItemIn

PRAGUE = ZoneInfo("Europe/Prague")


class TextImport(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


class GitHubImport(BaseModel):
    repository: str = Field(min_length=3, max_length=300)


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    reference: str
    excerpt: str
    proposed: ProfileItemIn
    confirmed_item_id: uuid.UUID | None


class Confirmation(BaseModel):
    item: ProfileItemIn
    evidence_kind: Literal["claimed", "demonstrated"] = "claimed"
    confirmed: Literal[True]


class Completion(Confirmation):
    target_type: Literal["opportunity", "action"]
    target_id: uuid.UUID
    evidence_kind: Literal["demonstrated"] = "demonstrated"

    @model_validator(mode="after")
    def outcome(self):
        if not self.item.result or not self.item.result.strip() or not self.item.achieved_on:
            raise ValueError("Vyplň výsledek a datum dokončení.")
        if self.item.achieved_on > datetime.now(PRAGUE).date():
            raise ValueError("Výsledek nemůže být v budoucnosti.")
        return self


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    goal_id: uuid.UUID
    reason: str
    coverage: dict[str, float]
    created_at: datetime


class PlanIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    target_type: Literal["opportunity", "action"] | None = None
    target_id: uuid.UUID | None = None
    est_hours: float = Field(gt=0, le=168)
    week_of: date
    status: Literal["planned", "in_progress", "done", "cancelled"] = "planned"
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def dates(self):
        if bool(self.target_type) != bool(self.target_id):
            raise ValueError("Typ a ID akce musí být vyplněny společně.")
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("Vyplň začátek i konec.")
        if self.starts_at and self.ends_at:
            # Google Calendar keeps whole seconds; sub-second parts would never compare equal.
            self.starts_at = self.starts_at.replace(microsecond=0)
            self.ends_at = self.ends_at.replace(microsecond=0)
            if self.ends_at <= self.starts_at:
                raise ValueError("Konec musí být po začátku.")
        return self


class PlanOut(PlanIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    updated_at: datetime
    conflict: dict | None


class WeekOut(BaseModel):
    week_of: date
    plans: list[PlanOut]
    planned_hours: float
    budget_hours: int | None
    over_budget: bool
