import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.opportunities.models import Opportunity
from app.sources.base import NormalizedOpportunity
from app.sources.devpost import DevpostSource, parse_prize_usd, parse_submission_end
from app.sources.models import SourceRun
from app.sources.runner import run_sources

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
PAGES = json.loads(
    (Path(__file__).parent / "fixtures" / "devpost_hackathons.json").read_text(encoding="utf-8")
)["pages"]


def _client(pages: list[dict], calls: list[int] | None = None, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if calls is not None:
            calls.append(page)
        if status != 200:
            return httpx.Response(status)
        body = pages[page - 1] if page <= len(pages) else {"hackathons": []}
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _by_ref(items: list[NormalizedOpportunity]) -> dict[str, NormalizedOpportunity]:
    return {i.source_ref: i for i in items}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Jul 31 - Oct 01, 2026", datetime(2026, 10, 1, tzinfo=UTC)),
        ("Sep 05 - 30, 2026", datetime(2026, 9, 30, tzinfo=UTC)),
        ("Aug 23, 2026 - Jan 02, 2027", datetime(2027, 1, 2, tzinfo=UTC)),
        ("Sep 27, 2026", datetime(2026, 9, 27, tzinfo=UTC)),
        ("Dates TBA", None),
        ("Foo 31 - Oct 01, 2026", datetime(2026, 10, 1, tzinfo=UTC)),
        ("Foo 05 - 30, 2026", None),
        ("Feb 01 - 30, 2026", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_submission_end(raw: str | None, expected: datetime | None) -> None:
    assert parse_submission_end(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$<span data-currency-value>740,000</span>", 740_000),
        ("€ <span data-currency-value>12,000</span>", 13_200),
        ("₹ <span data-currency-value>15,000</span>", None),
        ("$CAD <span data-currency-value>5,000</span>", None),
        ("", None),
    ],
)
def test_parse_prize_usd(raw: str, expected: float | None) -> None:
    assert parse_prize_usd(raw) == (pytest.approx(expected) if expected is not None else None)


def test_fetch_filters_and_maps() -> None:
    items = _by_ref(DevpostSource(_client(PAGES)).fetch(NOW))

    # ML/AI + (online | Europe), not invite-only, deadline not passed
    assert set(items) == {"30992", "30408", "31024", "30740", "31249", "31493", "90001", "90004"}

    amazon = items["30992"]
    assert amazon.kind == "hackathon"
    assert amazon.source == "devpost"
    assert amazon.deadline_at == datetime(2026, 10, 23, tzinfo=UTC)
    assert amazon.eligibility.verified is False
    assert amazon.cost_eur is None
    assert amazon.cv_signal == 3  # prize >= 10k USD
    assert {"hackathon_result", "teamwork", "deep_learning"} <= set(amazon.signals)
    assert str(amazon.evidence_url) == str(amazon.url)

    assert items["31493"].cv_signal == 2  # ₹ prize is not converted → default
    assert items["90001"].location == "Prague, Czech Republic"
    assert items["90004"].deadline_at is None  # unparseable → not published, never guessed
    assert "frontend" in items["31024"].signals  # Web theme


def test_fetch_stops_on_empty_page() -> None:
    calls: list[int] = []
    DevpostSource(_client(PAGES, calls)).fetch(NOW)
    assert calls == [1, 2, 3]


def test_fetch_without_client_fails_loudly() -> None:
    with pytest.raises(RuntimeError):
        DevpostSource(None).fetch(NOW)


def test_http_error_is_reported_per_source(session: Session) -> None:
    report = run_sources(session, NOW, [DevpostSource(_client(PAGES, status=503))])
    [source] = report.sources
    assert source.status == "error"
    assert "503" in (source.error or "")
    run = session.scalars(select(SourceRun)).one()
    assert (run.source, run.status) == ("devpost", "error")


def test_run_persists_devpost_items(session: Session, client: TestClient) -> None:
    report = run_sources(session, NOW, [DevpostSource(_client(PAGES))])
    assert report.sources[0].status == "ok"
    assert report.sources[0].result.created == 8
    rows = session.scalars(select(Opportunity).where(Opportunity.source == "devpost")).all()
    assert len(rows) == 8

    statuses = {s["id"]: s for s in client.get("/sources").json()}
    assert statuses["devpost"]["last_status"] == "ok"
    assert statuses["devpost"]["last_fetched"] == 8
    assert statuses["devpost"]["enabled"] is False  # tests run with SOURCES_ENABLED=curated
    assert statuses["curated"]["last_run"] is None


def test_not_configured_adapter_is_skipped(session: Session) -> None:
    class Unconfigured(DevpostSource):
        id = "unconfigured"
        configured = False

        def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
            raise AssertionError("must not be called")

    report = run_sources(session, NOW, [Unconfigured(None)])
    assert report.sources[0].status == "not_configured"
    assert session.scalars(select(SourceRun)).one().status == "not_configured"
