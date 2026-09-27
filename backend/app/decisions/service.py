import uuid
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.common import utcnow
from app.decisions.models import Decision
from app.decisions.schemas import DecisionIn, TargetType
from app.opportunities.models import GrowthAction, Opportunity
from app.profile.models import Profile


def target_exists(session: Session, data: DecisionIn) -> bool:
    model = Opportunity if data.target_type == TargetType.OPPORTUNITY else GrowthAction
    return session.get(model, data.target_id) is not None


def record_decision(session: Session, profile: Profile, data: DecisionIn) -> Decision:
    # Keep created_at strictly increasing so "latest decision" never depends on clock resolution.
    now = utcnow()
    last = session.scalar(
        select(func.max(Decision.created_at)).where(Decision.profile_id == profile.id)
    )
    if last is not None and now <= last:
        now = last + timedelta(microseconds=1)
    decision = Decision(
        profile_id=profile.id,
        target_type=data.target_type.value,
        target_id=data.target_id,
        status=data.status.value,
        note=data.note,
        created_at=now,
    )
    session.add(decision)
    session.commit()
    return decision


def clear_decisions(
    session: Session, profile: Profile, target_type: TargetType, target_id: uuid.UUID
) -> int:
    """Undo: forget every decision about a target, so it is undecided again."""
    result = session.execute(
        delete(Decision).where(
            Decision.profile_id == profile.id,
            Decision.target_type == target_type.value,
            Decision.target_id == target_id,
        )
    )
    session.commit()
    return result.rowcount


def list_decisions(session: Session, profile: Profile) -> list[Decision]:
    stmt = (
        select(Decision)
        .where(Decision.profile_id == profile.id)
        .order_by(Decision.created_at.desc(), Decision.id)
    )
    return list(session.scalars(stmt))


def latest_decisions(session: Session, profile: Profile) -> dict[str, str]:
    """Effective decision per target, keyed like ranking candidates: "<type>:<id>"."""
    latest: dict[str, str] = {}
    for decision in list_decisions(session, profile):  # newest first
        latest.setdefault(f"{decision.target_type}:{decision.target_id}", decision.status)
    return latest
