"""Idempotent development seed: `uv run python -m app.seed`.

Creates the single profile from data/seed/profile.yaml and one goal per template
(first template active) — only when they don't exist yet. Never overwrites user edits.
"""

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.goals.schemas import GoalCreate
from app.goals.service import create_goal, list_goals
from app.profile.models import Profile
from app.profile.schemas import ProfileItemIn, ProfileSkillIn, ProfileUpdate
from app.profile.service import add_item, get_profile, replace_skills, update_profile
from app.taxonomy import DATA_DIR, load_goal_templates

DEFAULT_ACTIVE_TEMPLATE = "ai_ml_internship"


def seed_profile(session: Session) -> tuple[Profile, bool]:
    existing = get_profile(session)
    if existing is not None:
        return existing, False
    raw = yaml.safe_load((DATA_DIR / "seed" / "profile.yaml").read_text(encoding="utf-8"))
    # Validate everything first so an invalid file never leaves a half-seeded profile.
    fields = ProfileUpdate.model_validate(raw)
    skills = [ProfileSkillIn.model_validate(s) for s in raw.get("skills", [])]
    items = [ProfileItemIn.model_validate(i) for i in raw.get("items", [])]

    profile = Profile(name=fields.name)
    session.add(profile)
    session.flush()
    update_profile(session, profile, fields)
    replace_skills(session, profile, skills)
    for item in items:
        add_item(session, profile, item)
    return profile, True


def seed_goals(session: Session, profile: Profile) -> int:
    if list_goals(session, profile):
        return 0
    created = 0
    for template_id in load_goal_templates():
        active = template_id == DEFAULT_ACTIVE_TEMPLATE
        create_goal(session, profile, GoalCreate(template_id=template_id, active=active))
        created += 1
    return created


def run() -> dict[str, object]:
    with SessionLocal() as session:
        profile, profile_created = seed_profile(session)
        goals_created = seed_goals(session, profile)
    return {"profile_created": profile_created, "goals_created": goals_created}


if __name__ == "__main__":
    print(run())
