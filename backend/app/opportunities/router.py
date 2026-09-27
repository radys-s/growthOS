from fastapi import APIRouter

from app.common import utcnow
from app.db import DbSession
from app.opportunities.schemas import OpportunityOut
from app.opportunities.service import list_open_opportunities, to_out
from app.sources.runner import RunReport, run_sources

router = APIRouter(tags=["opportunities"])


@router.get("/opportunities", response_model=list[OpportunityOut])
def get_opportunities(session: DbSession) -> list[OpportunityOut]:
    now = utcnow()
    return [to_out(row, now) for row in list_open_opportunities(session)]


@router.post("/sources/run", response_model=RunReport)
def post_run_sources(session: DbSession) -> RunReport:
    return run_sources(session, utcnow())
