import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import select

from app.common import utcnow
from app.db import DbSession
from app.decisions.models import Decision
from app.decisions.schemas import DecisionIn, DecisionOut, DecisionStatus
from app.decisions.service import latest_decisions, record_decision
from app.growth.imports import MAX_BYTES, document_text, github_text, propose
from app.growth.locking import WRITE_LOCK
from app.growth.models import ImportProposal, PlannedAction, ProgressSnapshot
from app.growth.schemas import (
    Completion,
    Confirmation,
    GitHubImport,
    PlanIn,
    PlanOut,
    ProposalOut,
    SnapshotOut,
    TextImport,
    WeekOut,
)
from app.growth.service import confirm_item
from app.opportunities.models import GrowthAction, Opportunity
from app.profile.models import ProfileItem
from app.profile.schemas import ProfileItemOut
from app.profile.service import get_or_create_profile

router = APIRouter(tags=["growth"])


@router.post("/imports/text", response_model=list[ProposalOut])
def text_preview(data: TextImport, session: DbSession):
    with WRITE_LOCK:
        return propose(session, get_or_create_profile(session), "cv", "Vložený text CV", data.text)


@router.post("/imports/file", response_model=list[ProposalOut])
def file_preview(file: UploadFile, session: DbSession):
    # Sync handler: parsing and the write lock run in the threadpool, not on the event loop.
    content = file.file.read(MAX_BYTES + 1)
    text = document_text(file.filename or "", content)
    with WRITE_LOCK:
        return propose(
            session,
            get_or_create_profile(session),
            "cv",
            (file.filename or "CV")[:300],
            text,
        )


@router.post("/imports/github", response_model=list[ProposalOut])
def github_preview(data: GitHubImport, session: DbSession):
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        title, reference, text = github_text(data.repository, client)
    with WRITE_LOCK:
        return propose(session, get_or_create_profile(session), "github", reference, text, title)


@router.post("/imports/{proposal_id}/confirm", response_model=ProfileItemOut)
def confirm(proposal_id: uuid.UUID, data: Confirmation, session: DbSession):
    with WRITE_LOCK:
        profile = get_or_create_profile(session)
        proposal = session.get(ImportProposal, proposal_id)
        if not proposal or proposal.profile_id != profile.id:
            raise HTTPException(404, "Návrh nenalezen.")
        if proposal.confirmed_item_id:
            item = session.get(ProfileItem, proposal.confirmed_item_id)
            if not item:
                raise HTTPException(409, "Tento import již byl potvrzen a později odstraněn.")
            return item
        if data.evidence_kind == "demonstrated" and not (data.item.result or "").strip():
            raise HTTPException(422, "Doložený výsledek vyžaduje konkrétní popis výsledku.")
        item = confirm_item(
            session,
            profile,
            data,
            "import:" + proposal.fingerprint,
            {
                "source": proposal.source,
                "reference": proposal.reference,
                "excerpt": proposal.excerpt,
                "confirmed_at": utcnow().isoformat(),
            },
        )
        proposal.confirmed_item_id = item.id
        session.commit()
        return item


@router.post("/completions", response_model=ProfileItemOut)
def completion(data: Completion, session: DbSession):
    with WRITE_LOCK:
        profile = get_or_create_profile(session)
        target = session.get(
            Opportunity if data.target_type == "opportunity" else GrowthAction, data.target_id
        )
        if not target:
            raise HTTPException(404, "Akce nenalezena.")
        key = f"completion:{data.target_type}:{data.target_id}"
        item = confirm_item(
            session,
            profile,
            data,
            key,
            {
                "source": "completion",
                "reference": key,
                "excerpt": data.item.result,
                "confirmed_at": utcnow().isoformat(),
            },
        )
        for plan in session.scalars(
            select(PlannedAction).where(
                PlannedAction.profile_id == profile.id,
                PlannedAction.target_type == data.target_type,
                PlannedAction.target_id == data.target_id,
            )
        ):
            plan.status = "done"
        # Latest effective decision, so a reversed "done" is recorded again.
        if latest_decisions(session, profile).get(f"{data.target_type}:{data.target_id}") != "done":
            record_decision(  # commits everything above in one transaction
                session,
                profile,
                DecisionIn(
                    target_type=data.target_type,
                    target_id=data.target_id,
                    status=DecisionStatus.DONE,
                    note=(data.item.result or "")[:2000],
                ),
            )
        session.commit()
        return item


@router.get("/history", response_model=list[DecisionOut])
def history(session: DbSession):
    profile = get_or_create_profile(session)
    return list(
        session.scalars(
            select(Decision)
            .where(Decision.profile_id == profile.id)
            .order_by(Decision.created_at.desc())
        )
    )


@router.get("/progress", response_model=list[SnapshotOut])
def progress(session: DbSession):
    profile = get_or_create_profile(session)
    return list(
        session.scalars(
            select(ProgressSnapshot)
            .where(ProgressSnapshot.profile_id == profile.id)
            .order_by(ProgressSnapshot.created_at)
        )
    )


def normalize_week(data: PlanIn):
    day = (
        data.starts_at.astimezone(ZoneInfo("Europe/Prague")).date()
        if data.starts_at
        else data.week_of
    )
    data.week_of = day - timedelta(days=day.weekday())


@router.get("/plans", response_model=WeekOut)
def plans(session: DbSession, week_of: date | None = None):
    profile = get_or_create_profile(session)
    day = week_of or utcnow().astimezone(ZoneInfo("Europe/Prague")).date()
    start = day - timedelta(days=day.weekday())
    rows = list(
        session.scalars(
            select(PlannedAction)
            .where(PlannedAction.profile_id == profile.id, PlannedAction.week_of == start)
            .order_by(PlannedAction.starts_at.asc().nulls_last(), PlannedAction.title)
        )
    )
    hours = sum(p.est_hours for p in rows if p.status != "cancelled")
    budget = profile.weekly_hours_budget
    return WeekOut(
        week_of=start,
        plans=rows,
        planned_hours=hours,
        budget_hours=budget,
        over_budget=budget is not None and hours > budget,
    )


@router.post("/plans", response_model=PlanOut)
def create_plan(data: PlanIn, session: DbSession):
    with WRITE_LOCK:
        profile = get_or_create_profile(session)
        normalize_week(data)
        if data.target_id and not session.get(
            Opportunity if data.target_type == "opportunity" else GrowthAction, data.target_id
        ):
            raise HTTPException(404, "Akce nenalezena.")
        row = PlannedAction(profile_id=profile.id, **data.model_dump())
        session.add(row)
        session.commit()
        return row


@router.put("/plans/{plan_id}", response_model=PlanOut)
def update_plan(plan_id: uuid.UUID, data: PlanIn, session: DbSession):
    with WRITE_LOCK:
        profile = get_or_create_profile(session)
        row = session.get(PlannedAction, plan_id)
        if not row or row.profile_id != profile.id:
            raise HTTPException(404, "Plán nenalezen.")
        if row.conflict:
            raise HTTPException(409, "Nejdřív vyřeš konflikt s kalendářem.")
        normalize_week(data)
        if data.target_id and not session.get(
            Opportunity if data.target_type == "opportunity" else GrowthAction, data.target_id
        ):
            raise HTTPException(404, "Akce nenalezena.")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        session.commit()
        return row
