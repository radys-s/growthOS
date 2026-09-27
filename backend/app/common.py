"""Shared primitives used across modules."""

from datetime import UTC, datetime
from enum import StrEnum


class EducationLevel(StrEnum):
    HIGH_SCHOOL = "high_school"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


def utcnow() -> datetime:
    return datetime.now(UTC)
