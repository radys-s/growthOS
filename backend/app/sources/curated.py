"""Curated YAML source (ADR 0005): hand-researched, evidence-backed items in data/curated/."""

from datetime import UTC, date, datetime, time
from enum import StrEnum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.sources.base import NormalizedOpportunity
from app.taxonomy import DATA_DIR, SignalList

CURATED_DIR = DATA_DIR / "curated"
PRAGUE = ZoneInfo("Europe/Prague")


def to_utc(value: Any) -> Any:
    """YAML dates mean 23:59 Prague time; datetimes must carry a timezone."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must include a timezone (e.g. trailing Z)")
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime.combine(value, time(23, 59), tzinfo=PRAGUE).astimezone(UTC)
    return value


_DATE_FIELDS = ("deadline_at", "last_known_deadline", "starts_at", "ends_at")


def _load_list(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"{path.name}: expected a list of items")
    return raw


class CuratedSource:
    id = "curated"
    name = "Kurátorský seznam"

    def __init__(self, path: Path = CURATED_DIR / "opportunities.yaml") -> None:
        self.path = path

    def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
        items: list[NormalizedOpportunity] = []
        seen: set[str] = set()
        for raw in _load_list(self.path):
            ref = raw.pop("id", None)
            if not ref or ref in seen:
                raise ValueError(f"{self.path.name}: missing or duplicate id {ref!r}")
            seen.add(ref)
            for field in _DATE_FIELDS:
                if raw.get(field) is not None:
                    raw[field] = to_utc(raw[field])
            try:
                items.append(
                    NormalizedOpportunity.model_validate(
                        {**raw, "source": self.id, "source_ref": ref, "fetched_at": now}
                    )
                )
            except ValueError as exc:
                raise ValueError(f"{self.path.name}: item {ref!r} is invalid: {exc}") from exc
        return items


class ActionKind(StrEnum):
    BUILD = "build"
    LEARN = "learn"
    CERTIFY = "certify"
    PUBLISH = "publish"
    APPLY = "apply"


class CuratedAction(BaseModel):
    id: str
    kind: ActionKind
    title: str = Field(min_length=1)
    description: str | None = None
    signals: SignalList
    est_hours: int | None = Field(default=None, ge=0)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    cv_signal: int | None = Field(default=None, ge=1, le=5)
    cv_signal_reason: str | None = None
    url: HttpUrl | None = None

    @field_validator("signals")
    @classmethod
    def _not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("an action must provide at least one signal")
        return value


def load_curated_actions(path: Path = CURATED_DIR / "actions.yaml") -> list[CuratedAction]:
    actions = [CuratedAction.model_validate(raw) for raw in _load_list(path)]
    ids = [a.id for a in actions]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate action id")
    return actions
