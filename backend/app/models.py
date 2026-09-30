"""Import every ORM model so Base.metadata is complete (Alembic, tests)."""

from app.decisions.models import Decision
from app.goals.models import Goal
from app.opportunities.models import GrowthAction, Opportunity
from app.profile.models import Profile, ProfileItem, ProfileSkill
from app.sources.models import SourceRun

__all__ = [
    "Decision",
    "Goal",
    "GrowthAction",
    "Opportunity",
    "Profile",
    "ProfileItem",
    "ProfileSkill",
    "SourceRun",
]

from app.calendar.models import CalendarConnection  # noqa: F401
from app.gmail.models import GmailConnection, GmailMessage  # noqa: F401
from app.growth.models import ImportProposal, PlannedAction, ProgressSnapshot  # noqa: F401
