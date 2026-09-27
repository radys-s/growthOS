import uuid

from fastapi import APIRouter, HTTPException, Query

from app.common import utcnow
from app.db import DbSession
from app.goals.service import get_active_goal, get_goal
from app.profile.service import get_or_create_profile
from app.ranking.engine import GapItem
from app.recommendations.service import Recommendations, gaps_for, recommend

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations", response_model=Recommendations)
def get_recommendations(
    session: DbSession,
    goal_id: uuid.UUID | None = None,
    top_n: int = Query(default=5, ge=1, le=20),
) -> Recommendations:
    profile = get_or_create_profile(session)
    goal = get_goal(session, profile, goal_id) if goal_id else get_active_goal(session, profile)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found — create or activate one")
    return recommend(session, profile, goal, utcnow(), top_n=top_n)


@router.get("/goals/{goal_id}/gaps", response_model=list[GapItem])
def get_goal_gaps(goal_id: uuid.UUID, session: DbSession) -> list[GapItem]:
    profile = get_or_create_profile(session)
    goal = get_goal(session, profile, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return gaps_for(goal, profile)
