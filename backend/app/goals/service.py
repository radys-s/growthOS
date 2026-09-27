import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.goals.models import Goal
from app.goals.schemas import GoalCreate, GoalUpdate
from app.profile.models import Profile
from app.taxonomy import load_goal_templates


class UnknownTemplateError(ValueError):
    pass


def list_goals(session: Session, profile: Profile) -> list[Goal]:
    stmt = select(Goal).where(Goal.profile_id == profile.id).order_by(Goal.created_at)
    return list(session.scalars(stmt))


def get_goal(session: Session, profile: Profile, goal_id: uuid.UUID) -> Goal | None:
    goal = session.get(Goal, goal_id)
    return goal if goal is not None and goal.profile_id == profile.id else None


def get_active_goal(session: Session, profile: Profile) -> Goal | None:
    stmt = select(Goal).where(Goal.profile_id == profile.id, Goal.active.is_(True)).limit(1)
    return session.scalars(stmt).first()


def _deactivate_others(session: Session, profile: Profile, keep: uuid.UUID) -> None:
    session.execute(
        update(Goal).where(Goal.profile_id == profile.id, Goal.id != keep).values(active=False)
    )


def create_goal(session: Session, profile: Profile, data: GoalCreate) -> Goal:
    template = load_goal_templates().get(data.template_id)
    if template is None:
        raise UnknownTemplateError(data.template_id)
    has_goals = bool(list_goals(session, profile))
    goal = Goal(
        profile_id=profile.id,
        template_id=template.id,
        title=data.title or template.title,
        target_date=data.target_date,
        required_signals=[r.model_dump() for r in template.required_signals],
        weights=template.weights.model_dump(),
        active=data.active or not has_goals,
    )
    session.add(goal)
    session.flush()
    if goal.active:
        _deactivate_others(session, profile, goal.id)
    session.commit()
    return goal


def update_goal(session: Session, profile: Profile, goal: Goal, data: GoalUpdate) -> Goal:
    changes = data.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is not None:
        goal.title = changes["title"]
    if "target_date" in changes:
        goal.target_date = changes["target_date"]
    if data.required_signals is not None:
        goal.required_signals = [r.model_dump() for r in data.required_signals]
    if data.weights is not None:
        goal.weights = data.weights.model_dump()
    if data.active is not None:
        goal.active = data.active
        if data.active:
            _deactivate_others(session, profile, goal.id)
    session.commit()
    session.refresh(goal)
    return goal


def delete_goal(session: Session, profile: Profile, goal: Goal) -> None:
    """Delete a goal; if it was the active one, the oldest remaining goal becomes active."""
    was_active = goal.active
    session.delete(goal)
    session.flush()
    if was_active:
        remaining = list_goals(session, profile)
        if remaining:
            remaining[0].active = True
    session.commit()
