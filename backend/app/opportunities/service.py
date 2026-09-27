from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.opportunities.deadlines import deadline_info
from app.opportunities.models import GrowthAction, Opportunity
from app.opportunities.schemas import OpportunityOut
from app.sources.base import Eligibility, NormalizedOpportunity
from app.sources.curated import CuratedAction


class UpsertResult(BaseModel):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    closed: int = 0
    duplicates: int = 0


def _values(item: NormalizedOpportunity) -> dict[str, Any]:
    return {
        "kind": item.kind.value,
        "title": item.title,
        "organizer": item.organizer,
        "url": str(item.url),
        "description": item.description,
        "deadline_at": item.deadline_at,
        "recurrence": item.recurrence.value if item.recurrence else None,
        "last_known_deadline": item.last_known_deadline,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "eligibility": item.eligibility.model_dump(mode="json"),
        "cost_eur": item.cost_eur,
        "location": item.location,
        "difficulty": item.difficulty,
        "est_hours": item.est_hours,
        "signals": list(item.signals),
        "cv_signal": item.cv_signal,
        "cv_signal_reason": item.cv_signal_reason,
        "evidence_url": str(item.evidence_url),
        "dedup_key": item.dedup_key,
        "status": "open",
    }


def upsert_opportunities(
    session: Session, source: str, items: list[NormalizedOpportunity]
) -> UpsertResult:
    """Upsert one source's full snapshot. Items missing from the snapshot are closed."""
    result = UpsertResult()
    rows = session.scalars(select(Opportunity).where(Opportunity.source == source))
    existing = {o.source_ref: o for o in rows}
    snapshot_refs = {item.source_ref for item in items}
    seen: set[str] = set()
    for item in items:
        values = _values(item)
        row = existing.get(item.source_ref)
        if row is None:
            duplicate = session.scalars(
                select(Opportunity).where(Opportunity.dedup_key == item.dedup_key)
            ).first()
            if (
                duplicate is not None
                and duplicate.source == source
                and duplicate.source_ref not in snapshot_refs
            ):
                # Same item re-keyed within this source (e.g. renamed curated id): adopt it.
                existing.pop(duplicate.source_ref, None)
                duplicate.source_ref = item.source_ref
                row = duplicate
            elif duplicate is not None:
                result.duplicates += 1
                continue
        if row is None:
            row = Opportunity(
                source=source, source_ref=item.source_ref, fetched_at=item.fetched_at, **values
            )
            session.add(row)
            result.created += 1
        else:
            changed = {k: v for k, v in values.items() if getattr(row, k) != v}
            for key, value in changed.items():
                setattr(row, key, value)
            row.fetched_at = item.fetched_at
            if changed:
                result.updated += 1
            else:
                result.unchanged += 1
        seen.add(item.source_ref)
        session.flush()
    for ref, row in existing.items():
        if ref not in seen and row.status == "open":
            row.status = "closed"
            result.closed += 1
    session.commit()
    return result


def sync_actions(session: Session, actions: list[CuratedAction]) -> int:
    """Upsert curated actions by id; actions removed from the file become inactive."""
    existing = {a.source_ref: a for a in session.scalars(select(GrowthAction))}
    for action in actions:
        values = action.model_dump(mode="json", exclude={"id"})
        row = existing.pop(action.id, None)
        if row is None:
            session.add(GrowthAction(source_ref=action.id, active=True, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
            row.active = True
    for row in existing.values():
        row.active = False
    session.commit()
    return len(actions)


def list_open_opportunities(session: Session) -> list[Opportunity]:
    stmt = (
        select(Opportunity)
        .where(Opportunity.status == "open")
        .order_by(Opportunity.deadline_at.is_(None), Opportunity.deadline_at, Opportunity.title)
    )
    return list(session.scalars(stmt))


def list_active_actions(session: Session) -> list[GrowthAction]:
    stmt = select(GrowthAction).where(GrowthAction.active.is_(True)).order_by(GrowthAction.title)
    return list(session.scalars(stmt))


def to_out(row: Opportunity, now: datetime) -> OpportunityOut:
    return OpportunityOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        organizer=row.organizer,
        url=row.url,
        description=row.description,
        deadline=deadline_info(row.deadline_at, row.recurrence, row.last_known_deadline, now),
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        eligibility=Eligibility.model_validate(row.eligibility or {}),
        cost_eur=row.cost_eur,
        location=row.location,
        difficulty=row.difficulty,
        est_hours=row.est_hours,
        signals=row.signals,
        cv_signal=row.cv_signal,
        cv_signal_reason=row.cv_signal_reason,
        source=row.source,
        evidence_url=row.evidence_url,
        fetched_at=row.fetched_at,
        first_seen_at=row.first_seen_at,
    )
