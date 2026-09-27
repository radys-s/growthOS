"""Controlled signal taxonomy and goal templates (ADR 0005), loaded from backend/data/."""

import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import AfterValidator, BaseModel, Field, model_validator

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SignalCategory(StrEnum):
    SKILL = "skill"
    EVIDENCE = "evidence"
    CREDENTIAL = "credential"


class Signal(BaseModel):
    id: str
    label: str
    category: SignalCategory
    aliases: list[str] = Field(default_factory=list)


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


class Taxonomy(BaseModel):
    signals: list[Signal]

    @model_validator(mode="after")
    def _unique(self) -> "Taxonomy":
        seen: set[str] = set()
        for signal in self.signals:
            for name in [signal.id, *signal.aliases]:
                key = _key(name)
                if key in seen:
                    raise ValueError(f"duplicate signal id/alias: {name}")
                seen.add(key)
        return self

    @property
    def by_id(self) -> dict[str, Signal]:
        return {s.id: s for s in self.signals}

    def resolve(self, value: str) -> str:
        key = _key(value)
        for signal in self.signals:
            if key == _key(signal.id) or key in (_key(a) for a in signal.aliases):
                return signal.id
        raise ValueError(f"unknown signal '{value}' (see backend/data/taxonomy.yaml)")


@lru_cache
def load_taxonomy() -> Taxonomy:
    raw = yaml.safe_load((DATA_DIR / "taxonomy.yaml").read_text(encoding="utf-8"))
    return Taxonomy.model_validate(raw)


def _resolve_signal(value: str) -> str:
    return load_taxonomy().resolve(value)


def _resolve_signals(values: list[str]) -> list[str]:
    resolved = [_resolve_signal(v) for v in values]
    return list(dict.fromkeys(resolved))


SignalId = Annotated[str, AfterValidator(_resolve_signal)]
SignalList = Annotated[list[str], AfterValidator(_resolve_signals)]


class FactorWeights(BaseModel):
    relevance: float = Field(ge=0)
    gap_coverage: float = Field(ge=0)
    cv_signal: float = Field(ge=0)
    skill_gain: float = Field(ge=0)
    probability: float = Field(ge=0)
    urgency: float = Field(ge=0)
    effort: float = Field(ge=0)
    cost: float = Field(ge=0)


class RequiredSignal(BaseModel):
    signal: SignalId
    importance: int = Field(ge=1, le=3)


class GoalTemplate(BaseModel):
    id: str
    title: str
    description: str
    kind: str
    required_signals: list[RequiredSignal]
    weights: FactorWeights

    @model_validator(mode="after")
    def _unique_signals(self) -> "GoalTemplate":
        ids = [r.signal for r in self.required_signals]
        if len(ids) != len(set(ids)):
            raise ValueError(f"template {self.id}: duplicate required signal")
        return self


@lru_cache
def load_goal_templates() -> dict[str, GoalTemplate]:
    templates: dict[str, GoalTemplate] = {}
    for path in sorted((DATA_DIR / "goal_templates").glob("*.yaml")):
        template = GoalTemplate.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        templates[template.id] = template
    return templates
