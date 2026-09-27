"""Source adapter contract (ADR 0004, 0005).

Every external or curated source implements ``SourceAdapter`` and returns
``NormalizedOpportunity`` items. Adapters are pure: they fetch and normalize,
they never write to the database.
"""

import re
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, computed_field

from app.common import EducationLevel
from app.taxonomy import SignalList


class OpportunityKind(StrEnum):
    COMPETITION = "competition"
    OLYMPIAD = "olympiad"
    HACKATHON = "hackathon"
    INTERNSHIP = "internship"
    SCHOLARSHIP = "scholarship"
    PROGRAM = "program"
    SUMMER_SCHOOL = "summer_school"
    CERTIFICATION = "certification"


class Recurrence(StrEnum):
    YEARLY = "yearly"
    ROLLING = "rolling"


class Eligibility(BaseModel):
    """Structured eligibility.

    ``verified=True``: the rules were checked at the evidence URL; a ``None`` field then means
    "no restriction". ``verified=False``: ``None`` means unknown and ranking treats the item as
    unverified (lower probability + warning).
    """

    verified: bool = False
    min_age: int | None = Field(default=None, ge=0)
    max_age: int | None = Field(default=None, ge=0)
    education_levels: list[EducationLevel] | None = None
    countries: list[str] | None = Field(default=None, description="ISO 3166-1 alpha-2 codes")
    team_size_min: int | None = Field(default=None, ge=1)
    team_size_max: int | None = Field(default=None, ge=1)
    notes: str | None = None


def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


class NormalizedOpportunity(BaseModel):
    kind: OpportunityKind
    title: str = Field(min_length=1)
    organizer: str = Field(min_length=1)
    url: HttpUrl
    description: str | None = None
    deadline_at: AwareDatetime | None = Field(
        default=None, description="UTC. Only when officially published; never guessed."
    )
    recurrence: Recurrence | None = None
    last_known_deadline: AwareDatetime | None = Field(
        default=None, description="Previous edition's deadline (evidence-backed)."
    )
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    eligibility: Eligibility = Field(default_factory=Eligibility)
    cost_eur: int | None = Field(default=None, ge=0, description="0 = free, None = unknown")
    location: str = "online"
    difficulty: int | None = Field(default=None, ge=1, le=5)
    est_hours: int | None = Field(default=None, ge=0)
    signals: SignalList = Field(default_factory=list)
    cv_signal: int | None = Field(default=None, ge=1, le=5)
    cv_signal_reason: str | None = None
    source: str
    source_ref: str
    evidence_url: HttpUrl
    watch_url: HttpUrl | None = Field(
        default=None,
        description="Official page where the next edition's deadline appears (deadline watcher).",
    )
    fetched_at: AwareDatetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dedup_key(self) -> str:
        deadline = self.deadline_at.date().isoformat() if self.deadline_at else "none"
        return f"{normalize_text(self.title)}|{normalize_text(self.organizer)}|{deadline}"


@runtime_checkable
class SourceAdapter(Protocol):
    id: str
    name: str

    def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
        """Fetch and normalize opportunities. ``now`` is UTC, injected for testability."""
        ...
