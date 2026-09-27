"""Import every ORM model so Base.metadata is complete (Alembic, tests)."""

from app.goals.models import Goal
from app.opportunities.models import GrowthAction, Opportunity
from app.profile.models import Profile, ProfileItem, ProfileSkill

__all__ = ["Goal", "GrowthAction", "Opportunity", "Profile", "ProfileItem", "ProfileSkill"]
