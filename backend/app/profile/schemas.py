import uuid
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.common import EducationLevel
from app.taxonomy import SignalId, SignalList


class ProfileItemKind(StrEnum):
    PROJECT = "project"
    COMPETITION = "competition"
    ACHIEVEMENT = "achievement"
    CERTIFICATION = "certification"
    EXPERIENCE = "experience"
    PUBLICATION = "publication"


class ProfileSkillIn(BaseModel):
    signal: SignalId
    level: int = Field(ge=0, le=4)


class ProfileSkillOut(BaseModel):
    """Output models use plain strings: stored data must stay readable if the taxonomy changes."""

    model_config = ConfigDict(from_attributes=True)

    signal: str
    level: int


class ProfileItemIn(BaseModel):
    kind: ProfileItemKind
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    result: str | None = Field(default=None, max_length=200)
    url: HttpUrl | None = None
    signals: SignalList = Field(default_factory=list)
    strength: int = Field(ge=0, le=4)
    achieved_on: date | None = None


class ProfileItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ProfileItemKind
    title: str
    description: str | None
    result: str | None
    url: str | None
    signals: list[str]
    strength: int
    achieved_on: date | None


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    birth_date: date | None = None
    country: str = Field(min_length=2, max_length=2)
    education_level: EducationLevel
    graduation_year: int | None = Field(default=None, ge=2000, le=2100)
    max_cost_eur: int | None = Field(default=None, ge=0)
    weekly_hours_budget: int | None = Field(default=None, ge=1, le=80)

    @field_validator("country")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    birth_date: date | None
    country: str
    education_level: EducationLevel
    graduation_year: int | None
    max_cost_eur: int | None
    weekly_hours_budget: int | None
    skills: list[ProfileSkillOut]
    items: list[ProfileItemOut]
