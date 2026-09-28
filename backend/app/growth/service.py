import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.goals.models import Goal
from app.growth.models import ProgressSnapshot
from app.growth.schemas import Confirmation
from app.profile.models import Profile, ProfileItem
from app.profile.service import signal_coverage


def snapshot(session: Session, profile: Profile, reason: str) -> None:
    coverage = signal_coverage(profile)
    for goal in session.scalars(select(Goal).where(Goal.profile_id == profile.id)):
        session.add(
            ProgressSnapshot(
                profile_id=profile.id,
                goal_id=goal.id,
                reason=reason,
                coverage={r["signal"]: coverage.get(r["signal"], 0) for r in goal.required_signals},
            )
        )
    session.flush()


def confirm_item(
    session: Session, profile: Profile, data: Confirmation, key: str, provenance: dict
) -> ProfileItem:
    key = hashlib.sha256(f"{profile.id}:{key}".encode()).hexdigest()
    existing = session.scalar(select(ProfileItem).where(ProfileItem.import_key == key))
    if existing:
        return existing
    snapshot(session, profile, "Před potvrzením: " + data.item.title)
    payload = data.item.model_dump(mode="json")
    payload["achieved_on"] = data.item.achieved_on
    row = ProfileItem(
        **payload,
        import_key=key,
        provenance=provenance,
        confirmation_state="confirmed",
        evidence_kind=data.evidence_kind,
    )
    profile.items.append(row)
    session.flush()
    snapshot(session, profile, "Potvrzen výsledek: " + row.title)
    return row
