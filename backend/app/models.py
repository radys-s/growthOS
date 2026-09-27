"""Import every ORM model so Base.metadata is complete (Alembic, tests)."""

from app.goals.models import Goal
from app.profile.models import Profile, ProfileItem, ProfileSkill

__all__ = ["Goal", "Profile", "ProfileItem", "ProfileSkill"]
