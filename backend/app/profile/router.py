import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.db import DbSession
from app.profile import service
from app.profile.schemas import (
    ProfileItemIn,
    ProfileItemOut,
    ProfileOut,
    ProfileSkillIn,
    ProfileUpdate,
)
from app.taxonomy import Signal, load_taxonomy

router = APIRouter(tags=["profile"])


@router.get("/taxonomy", response_model=list[Signal])
def get_taxonomy() -> list[Signal]:
    return load_taxonomy().signals


@router.get("/profile", response_model=ProfileOut)
def get_profile(session: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(service.get_or_create_profile(session))


@router.put("/profile", response_model=ProfileOut)
def put_profile(data: ProfileUpdate, session: DbSession) -> ProfileOut:
    profile = service.get_or_create_profile(session)
    return ProfileOut.model_validate(service.update_profile(session, profile, data))


@router.put("/profile/skills", response_model=ProfileOut)
def put_skills(skills: list[ProfileSkillIn], session: DbSession) -> ProfileOut:
    profile = service.get_or_create_profile(session)
    return ProfileOut.model_validate(service.replace_skills(session, profile, skills))


@router.post("/profile/items", response_model=ProfileItemOut, status_code=status.HTTP_201_CREATED)
def post_item(data: ProfileItemIn, session: DbSession) -> ProfileItemOut:
    profile = service.get_or_create_profile(session)
    return ProfileItemOut.model_validate(service.add_item(session, profile, data))


@router.delete("/profile/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: uuid.UUID, session: DbSession) -> Response:
    profile = service.get_or_create_profile(session)
    if not service.delete_item(session, profile, item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
