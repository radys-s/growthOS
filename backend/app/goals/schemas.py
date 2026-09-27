import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.taxonomy import FactorWeights, RequiredSignal


class GoalCreate(BaseModel):
    template_id: str
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_date: date | None = None
    active: bool = True


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_date: date | None = None
    active: bool | None = None
    required_signals: list[RequiredSignal] | None = None
    weights: FactorWeights | None = None

    @model_validator(mode="after")
    def _unique_signals(self) -> "GoalUpdate":
        if self.required_signals is not None:
            ids = [r.signal for r in self.required_signals]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate required signal")
        return self


class RequiredSignalOut(BaseModel):
    signal: str
    importance: int


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: str
    title: str
    target_date: date | None
    required_signals: list[RequiredSignalOut]
    weights: FactorWeights
    active: bool
