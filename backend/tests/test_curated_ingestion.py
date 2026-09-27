from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.opportunities.deadlines import DeadlineKind, deadline_info, project_next
from app.opportunities.models import GrowthAction, Opportunity
from app.opportunities.service import sync_actions, upsert_opportunities
from app.sources.base import NormalizedOpportunity, SourceAdapter
from app.sources.curated import CuratedSource, load_curated_actions, to_utc
from app.sources.runner import run_sources

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _item(
    ref: str, title: str = "Soutěž", source: str = "curated", **extra
) -> NormalizedOpportunity:
    return NormalizedOpportunity.model_validate(
        {
            "kind": "competition",
            "title": title,
            "organizer": "Org",
            "url": "https://example.com",
            "source": source,
            "source_ref": ref,
            "evidence_url": "https://example.com/rules",
            "fetched_at": NOW,
            **extra,
        }
    )


# --- curated files ---------------------------------------------------------------


def test_curated_files_validate() -> None:
    items = CuratedSource().fetch(NOW)
    assert len(items) >= 10
    assert all(i.source == "curated" and i.evidence_url for i in items)
    assert len({i.dedup_key for i in items}) == len(items)
    assert load_curated_actions()


def test_to_utc_date_means_end_of_day_prague() -> None:
    assert to_utc(date(2026, 1, 15)) == datetime(2026, 1, 15, 22, 59, tzinfo=UTC)  # CET
    assert to_utc(date(2026, 7, 15)) == datetime(2026, 7, 15, 21, 59, tzinfo=UTC)  # CEST
    with pytest.raises(ValueError):
        to_utc(datetime(2026, 1, 1, 12, 0))


def test_curated_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "o.yaml"
    entry = (
        "- id: a\n  kind: hackathon\n  title: T\n  organizer: O\n"
        "  url: https://x.cz\n  evidence_url: https://x.cz\n"
    )
    path.write_text(entry + entry, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        CuratedSource(path).fetch(NOW)


# --- deadlines -------------------------------------------------------------------


def test_deadline_official_future() -> None:
    info = deadline_info(datetime(2026, 11, 1, tzinfo=UTC), None, None, NOW)
    assert info.kind == DeadlineKind.OFFICIAL
    assert info.label == "do 1. 11. 2026"
    # 23:30 UTC on 13 March is already 14 March in Prague.
    late = deadline_info(datetime(2027, 3, 13, 23, 30, tzinfo=UTC), None, None, NOW)
    assert late.label == "do 14. 3. 2027"


def test_deadline_rolling() -> None:
    assert deadline_info(None, "rolling", None, NOW).kind == DeadlineKind.ROLLING


def test_deadline_expected_from_last_known() -> None:
    info = deadline_info(None, "yearly", datetime(2026, 3, 13, tzinfo=UTC), NOW)
    assert info.kind == DeadlineKind.EXPECTED
    assert info.date == datetime(2027, 3, 13, tzinfo=UTC)
    assert "březen 2027" in info.label and "nezveřejněno" in info.label


def test_deadline_passed_yearly_becomes_expected() -> None:
    info = deadline_info(datetime(2026, 5, 1, tzinfo=UTC), "yearly", None, NOW)
    assert info.kind == DeadlineKind.EXPECTED
    assert info.date == datetime(2027, 5, 1, tzinfo=UTC)


def test_deadline_passed_non_recurring() -> None:
    assert deadline_info(datetime(2026, 5, 1, tzinfo=UTC), None, None, NOW).kind == "passed"


def test_deadline_unknown_never_invented() -> None:
    assert deadline_info(None, "yearly", None, NOW).date is None
    info = deadline_info(None, None, None, NOW)
    assert info.kind == DeadlineKind.UNKNOWN and info.date is None


def test_project_next_leap_day() -> None:
    assert project_next(datetime(2024, 2, 29, tzinfo=UTC), NOW) == datetime(2027, 2, 28, tzinfo=UTC)


# --- upsert ----------------------------------------------------------------------


def test_upsert_is_idempotent_and_updates(session: Session) -> None:
    first = upsert_opportunities(session, "curated", [_item("a"), _item("b", "Jiná")])
    assert (first.created, first.updated) == (2, 0)
    second = upsert_opportunities(session, "curated", [_item("a"), _item("b", "Jiná")])
    assert (second.created, second.unchanged) == (0, 2)
    third = upsert_opportunities(session, "curated", [_item("a", est_hours=10), _item("b", "Jiná")])
    assert third.updated == 1
    assert len(session.scalars(select(Opportunity)).all()) == 2


def test_upsert_closes_removed_and_reopens(session: Session) -> None:
    upsert_opportunities(session, "curated", [_item("a"), _item("b", "Jiná")])
    result = upsert_opportunities(session, "curated", [_item("a")])
    assert result.closed == 1
    row = session.scalars(select(Opportunity).where(Opportunity.source_ref == "b")).one()
    assert row.status == "closed"
    upsert_opportunities(session, "curated", [_item("a"), _item("b", "Jiná")])
    session.refresh(row)
    assert row.status == "open"


def test_upsert_skips_cross_source_duplicate(session: Session) -> None:
    upsert_opportunities(session, "curated", [_item("a")])
    result = upsert_opportunities(session, "kaggle", [_item("k1", source="kaggle")])
    assert result.duplicates == 1
    assert len(session.scalars(select(Opportunity)).all()) == 1


def test_upsert_adopts_renamed_id(session: Session) -> None:
    upsert_opportunities(session, "curated", [_item("old")])
    result = upsert_opportunities(session, "curated", [_item("new")])
    assert (result.created, result.duplicates, result.closed) == (0, 0, 0)
    row = session.scalars(select(Opportunity)).one()
    assert (row.source_ref, row.status) == ("new", "open")


def test_sync_actions_deactivates_removed(session: Session) -> None:
    actions = load_curated_actions()
    sync_actions(session, actions)
    sync_actions(session, actions[1:])
    rows = {a.source_ref: a for a in session.scalars(select(GrowthAction))}
    assert len(rows) == len(actions)
    assert rows[actions[0].id].active is False
    assert all(rows[a.id].active for a in actions[1:])


# --- runner + API ----------------------------------------------------------------


class _Broken:
    id = "broken"
    name = "Broken"

    def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
        raise RuntimeError("boom")


def test_runner_isolates_failing_source(session: Session) -> None:
    adapters: list[SourceAdapter] = [_Broken(), CuratedSource()]
    report = run_sources(session, NOW, adapters)
    assert report.sources[0].error == "boom"
    assert report.sources[1].result is not None and report.sources[1].result.created >= 10
    assert report.actions and report.actions_error is None


def test_api_run_and_list(client: TestClient) -> None:
    run = client.post("/sources/run")
    assert run.status_code == 200
    created = run.json()["sources"][0]["result"]["created"]
    again = client.post("/sources/run").json()["sources"][0]["result"]
    assert again["created"] == 0 and again["unchanged"] == created

    response = client.get("/opportunities")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == created
    ioai = next(o for o in body if "IOAI" in o["title"] or "Olympiad in AI" in o["title"])
    assert ioai["deadline"]["kind"] in {"official", "expected", "unknown", "rolling"}
    assert all(o["deadline"]["label"] for o in body)
