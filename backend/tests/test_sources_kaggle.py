"""Kaggle adapter against a fixture shaped like the v1 `competitions/list` response
(field names as in the official kaggle CLI's ApiCompetition)."""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.sources.kaggle import KaggleSource
from app.sources.runner import all_adapters, run_sources

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
PAGES = json.loads(
    (Path(__file__).parent / "fixtures" / "kaggle_competitions.json").read_text(encoding="utf-8")
)["pages"]


def _client(seen: list[httpx.Request], status: int = 200, wrap: bool = False) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if status != 200:
            return httpx.Response(status)
        page = int(request.url.params["page"])
        rows = PAGES[page - 1] if page <= len(PAGES) else []
        return httpx.Response(200, json={"competitions": rows} if wrap else rows)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("wrap", [False, True])
def test_fetch_maps_active_competitions(wrap: bool) -> None:
    seen: list[httpx.Request] = []
    items = {i.source_ref: i for i in KaggleSource(_client(seen, wrap=wrap), "u", "k").fetch(NOW)}

    assert set(items) == {"1001", "1002", "1003", "1004"}  # finished and deadline-less dropped
    featured = items["1001"]
    assert featured.kind == "competition"
    assert featured.deadline_at == datetime(2026, 12, 1, 23, 59, tzinfo=UTC)
    assert featured.cv_signal == 4
    assert featured.organizer == "Google"
    assert featured.cost_eur == 0
    assert featured.eligibility.verified is False
    assert {"ml_competition_result", "python", "computer_vision"} <= set(featured.signals)
    assert items["1002"].cv_signal == 2 and "classical_ml" in items["1002"].signals
    assert items["1003"].cv_signal == 1 and items["1003"].organizer == "Kaggle"
    assert "nlp" in items["1004"].signals

    assert [int(r.url.params["page"]) for r in seen] == [1, 2, 3]
    assert seen[0].headers["authorization"] == "Basic " + base64.b64encode(b"u:k").decode()


def test_not_configured_without_credentials(session: Session) -> None:
    assert KaggleSource(None, "", "").configured is False
    assert KaggleSource(None, "u", " ").configured is False
    report = run_sources(session, NOW, [KaggleSource(None, "", "")])
    assert report.sources[0].status == "not_configured"


def test_auth_error_reported(session: Session) -> None:
    report = run_sources(session, NOW, [KaggleSource(_client([], status=401), "u", "bad")])
    assert report.sources[0].status == "error"
    assert "401" in (report.sources[0].error or "")


def test_registered_with_settings() -> None:
    settings = Settings(kaggle_username="me", kaggle_key="secret")
    kaggle = next(a for a in all_adapters(settings, None) if a.id == "kaggle")
    assert kaggle.configured is True
