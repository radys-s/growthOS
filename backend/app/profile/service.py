import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.profile.models import Profile, ProfileItem, ProfileSkill
from app.profile.schemas import ProfileItemIn, ProfileSkillIn, ProfileUpdate


def get_profile(session: Session) -> Profile | None:
    """M1 is single-user: the profile is the oldest one."""
    return session.scalars(select(Profile).order_by(Profile.created_at).limit(1)).first()


def get_or_create_profile(session: Session) -> Profile:
    profile = get_profile(session)
    if profile is None:
        profile = Profile(name="Já")
        session.add(profile)
        session.commit()
    return profile


def update_profile(session: Session, profile: Profile, data: ProfileUpdate) -> Profile:
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    session.commit()
    return profile


def replace_skills(session: Session, profile: Profile, skills: list[ProfileSkillIn]) -> Profile:
    by_signal = {s.signal: s.level for s in skills}  # last value wins on duplicates
    profile.skills.clear()
    session.flush()
    profile.skills.extend(ProfileSkill(signal=sig, level=lvl) for sig, lvl in by_signal.items())
    session.commit()
    session.refresh(profile)
    return profile


def add_item(session: Session, profile: Profile, data: ProfileItemIn) -> ProfileItem:
    payload = data.model_dump(mode="json")
    payload["achieved_on"] = data.achieved_on
    item = ProfileItem(**payload)
    profile.items.append(item)
    session.commit()
    return item


def delete_item(session: Session, profile: Profile, item_id: uuid.UUID) -> bool:
    item = session.get(ProfileItem, item_id)
    if item is None or item.profile_id != profile.id:
        return False
    session.delete(item)
    session.commit()
    return True


def signal_coverage(profile: Profile) -> dict[str, float]:
    """Coverage of each signal in [0, 1]: max(skill level, strongest item proving it) / 4."""
    best: dict[str, int] = {}
    for skill in profile.skills:
        best[skill.signal] = max(best.get(skill.signal, 0), skill.level)
    for item in profile.items:
        for signal in item.signals:
            best[signal] = max(best.get(signal, 0), item.strength)
    return {signal: level / 4 for signal, level in best.items()}
