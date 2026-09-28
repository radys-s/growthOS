"""Glue between stored facts and the pure ranking engine."""

import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.credentials import Credential
from app.decisions.service import latest_decisions, list_decisions
from app.goals.models import Goal
from app.opportunities.deadlines import opportunity_deadline
from app.opportunities.models import GrowthAction, Opportunity
from app.opportunities.service import list_active_actions, list_open_opportunities
from app.profile.models import Profile
from app.profile.service import signal_coverage
from app.ranking.engine import (
    Candidate,
    FilteredItem,
    GapItem,
    GapSupport,
    GoalFacts,
    ProfileFacts,
    RankedItem,
    goal_gaps,
    rank,
)
from app.sources.base import Eligibility
from app.taxonomy import FactorWeights, load_taxonomy

NOVELTY_DAYS = 7


class Novelty(BaseModel):
    """Weekly success metric: did the engine surface something new and worth doing?"""

    window_days: int
    new_items: int  # first seen within the window
    new_worthwhile: int  # compatibility: explicitly useful only
    newly_discovered: int
    explicitly_useful: int
    already_knew: int  # new items the user marked "already knew"


class Recommendations(BaseModel):
    goal_id: uuid.UUID
    goal_title: str
    generated_at: datetime
    top: list[RankedItem]
    ranked: list[RankedItem]
    filtered: list[FilteredItem]
    novelty: Novelty


def profile_facts(profile: Profile) -> ProfileFacts:
    return ProfileFacts(
        birth_date=profile.birth_date,
        country=profile.country,
        education_level=profile.education_level,
        max_cost_eur=profile.max_cost_eur,
        weekly_hours_budget=profile.weekly_hours_budget,
        coverage=signal_coverage(profile),
    )


def goal_facts(goal: Goal) -> GoalFacts:
    return GoalFacts(
        required={r["signal"]: r["importance"] for r in goal.required_signals},
        weights=FactorWeights.model_validate(goal.weights),
    )


def gaps_for(goal: Goal, profile: Profile) -> list[GapItem]:
    gaps = goal_gaps(goal_facts(goal), signal_coverage(profile), load_taxonomy())
    for gap in gaps:
        gap.supports = [
            GapSupport(item_id=i.id, title=i.title, kind=i.evidence_kind, coverage=i.strength / 4)
            for i in profile.items
            if gap.signal in i.signals
            and i.confirmation_state == "confirmed"
            and i.evidence_kind == "demonstrated"
        ]
        gap.supports.extend(
            GapSupport(title="Ručně uvedená dovednost", kind="self_assessed", coverage=s.level / 4)
            for s in profile.skills
            if s.signal == gap.signal
        )
    return gaps


def _opportunity_candidate(
    row: Opportunity, decisions: dict[str, str], now: datetime, since: datetime
) -> Candidate:
    key = f"opportunity:{row.id}"
    return Candidate(
        key=key,
        source="opportunity",
        origin=row.source,
        target_id=row.id,
        kind=row.kind,
        title=row.title,
        organizer=row.organizer,
        description=row.description,
        url=row.url,
        signals=row.signals,
        cv_signal=row.cv_signal,
        cv_signal_reason=row.cv_signal_reason,
        difficulty=row.difficulty,
        est_hours=row.est_hours,
        cost_eur=row.cost_eur,
        deadline=opportunity_deadline(row, now),
        eligibility=Eligibility.model_validate(row.eligibility or {}),
        credential=(
            Credential(type=row.credential_type, issuer_reputation=row.issuer_reputation)
            if row.credential_type and row.issuer_reputation
            else None
        ),
        closed=row.status != "open",
        decision=decisions.get(key),
        is_new=row.first_seen_at >= since,
    )


def _action_candidate(row: GrowthAction, decisions: dict[str, str], since: datetime) -> Candidate:
    key = f"action:{row.id}"
    return Candidate(
        key=key,
        source="action",
        target_id=row.id,
        kind=row.kind,
        title=row.title,
        description=row.description,
        url=row.url,
        signals=row.signals,
        cv_signal=row.cv_signal,
        cv_signal_reason=row.cv_signal_reason,
        difficulty=row.difficulty,
        est_hours=row.est_hours,
        cost_eur=0,
        decision=decisions.get(key),
        is_new=row.first_seen_at >= since,
    )


def recommend(
    session: Session, profile: Profile, goal: Goal, now: datetime, top_n: int = 5
) -> Recommendations:
    decisions = latest_decisions(session, profile)
    since = now - timedelta(days=NOVELTY_DAYS)
    candidates = [
        _opportunity_candidate(row, decisions, now, since)
        for row in list_open_opportunities(session)
    ] + [_action_candidate(row, decisions, since) for row in list_active_actions(session)]
    result = rank(candidates, profile_facts(profile), goal_facts(goal), now, top_n=top_n)

    new = [c for c in candidates if c.is_new]
    useful = {
        f"{d.target_type}:{d.target_id}"
        for d in list_decisions(session, profile)
        if d.status == "useful" and d.created_at >= since
    }
    novelty = Novelty(
        window_days=NOVELTY_DAYS,
        new_items=len(new),
        new_worthwhile=len(useful),
        newly_discovered=sum(
            i.candidate.is_new and i.candidate.decision != "already_knew" for i in result.ranked
        ),
        explicitly_useful=len(useful),
        already_knew=sum(1 for c in new if c.decision == "already_knew"),
    )
    return Recommendations(
        goal_id=goal.id,
        goal_title=goal.title,
        generated_at=now,
        top=result.top,
        ranked=result.ranked,
        filtered=result.filtered,
        novelty=novelty,
    )
