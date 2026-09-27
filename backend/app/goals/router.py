import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.db import DbSession
from app.goals import service
from app.goals.schemas import GoalCreate, GoalOut, GoalUpdate
from app.profile.service import get_or_create_profile
from app.taxonomy import GoalTemplate, load_goal_templates

router = APIRouter(tags=["goals"])


@router.get("/goal-templates", response_model=list[GoalTemplate])
def get_templates() -> list[GoalTemplate]:
    return list(load_goal_templates().values())


@router.get("/goals", response_model=list[GoalOut])
def get_goals(session: DbSession) -> list[GoalOut]:
    profile = get_or_create_profile(session)
    return [GoalOut.model_validate(g) for g in service.list_goals(session, profile)]


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def post_goal(data: GoalCreate, session: DbSession) -> GoalOut:
    profile = get_or_create_profile(session)
    try:
        goal = service.create_goal(session, profile, data)
    except service.UnknownTemplateError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown goal template: {exc}") from exc
    return GoalOut.model_validate(goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def patch_goal(goal_id: uuid.UUID, data: GoalUpdate, session: DbSession) -> GoalOut:
    profile = get_or_create_profile(session)
    goal = service.get_goal(session, profile, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return GoalOut.model_validate(service.update_goal(session, profile, goal, data))


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: uuid.UUID, session: DbSession) -> Response:
    profile = get_or_create_profile(session)
    goal = service.get_goal(session, profile, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    service.delete_goal(session, profile, goal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
