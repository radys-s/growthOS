import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.db import DbSession
from app.decisions import service
from app.decisions.schemas import DecisionIn, DecisionOut, TargetType
from app.profile.service import get_or_create_profile

router = APIRouter(tags=["decisions"])


@router.post("/decisions", response_model=DecisionOut, status_code=status.HTTP_201_CREATED)
def post_decision(data: DecisionIn, session: DbSession) -> DecisionOut:
    if not service.target_exists(session, data):
        raise HTTPException(status_code=404, detail=f"{data.target_type.value} not found")
    profile = get_or_create_profile(session)
    return DecisionOut.model_validate(service.record_decision(session, profile, data))


@router.get("/decisions", response_model=list[DecisionOut])
def get_decisions(session: DbSession) -> list[DecisionOut]:
    profile = get_or_create_profile(session)
    return [DecisionOut.model_validate(d) for d in service.list_decisions(session, profile)]


@router.delete("/decisions/{target_type}/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_decisions(target_type: TargetType, target_id: uuid.UUID, session: DbSession) -> Response:
    profile = get_or_create_profile(session)
    if service.clear_decisions(session, profile, target_type, target_id) == 0:
        raise HTTPException(status_code=404, detail="No decision for this target")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
