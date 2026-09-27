import json
from datetime import UTC, date, datetime
from typing import TypeVar

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.openai_compat import OpenAICompatProvider
from app.ai.provider import ProviderError
from app.opportunities.models import Opportunity
from app.opportunities.service import upsert_opportunities
from app.sources.base import NormalizedOpportunity
from app.sources.deadline_watch import (
    DeadlineExtraction,
    date_in_quote,
    llm_excerpt,
    page_text,
    verify,
    watch_deadlines,
)
from app.sources.runner import run_sources

T = TypeVar("T", bound=BaseModel)
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
WATCH = "https://www.kasiopea.cz/"
PAGE = """<html><head><script>var deadline = "1. 1. 2030";</script></head><body>
<h1>Kasiopea 2026/27</h1>
<p>Domácí kolo probíhá online.</p>
<p>Kasiopea je programátorská soutěž pro středoškoláky, kteří se chtějí naučit řešit algoritmické úlohy a potkat podobně naladěné lidi.</p>
<p>Registrace do domácího kola je otevřena do&nbsp;15.&nbsp;11.&nbsp;2026 včetně.</p>
<p>Finále se koná 20. 2. 2027.</p></body></html>"""
QUOTE = "Registrace do domácího kola je otevřena do 15. 11. 2026 včetně."


class FakeLLM:
    name = "fake"

    def __init__(self, answer: DeadlineExtraction | Exception) -> None:
        self.answer = answer
        self.calls = 0

    def extract(self, text: str, schema: type[T], instructions: str) -> T:
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer  # type: ignore[return-value]


def _pages(html: str | None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503) if html is None else httpx.Response(200, text=html)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _item(**extra) -> NormalizedOpportunity:
    return NormalizedOpportunity.model_validate(
        {
            "kind": "competition",
            "title": "Kasiopea",
            "organizer": "KSP MFF UK",
            "url": "https://www.kasiopea.cz/",
            "source": "curated",
            "source_ref": "kasiopea",
            "evidence_url": "https://www.kasiopea.cz/",
            "watch_url": WATCH,
            "recurrence": "yearly",
            "fetched_at": NOW,
            **extra,
        }
    )


def _row(session: Session) -> Opportunity:
    return session.scalars(select(Opportunity).where(Opportunity.source_ref == "kasiopea")).one()


def _seed(session: Session, **extra) -> None:
    upsert_opportunities(session, "curated", [_item(**extra)])


def _answer(day: date | None = date(2026, 11, 15), quote: str | None = QUOTE):
    return DeadlineExtraction(deadline_date=day, quote=quote)


# --- verification ----------------------------------------------------------------------


def test_page_text_drops_scripts_and_keeps_lines() -> None:
    text = page_text(PAGE)
    assert "1. 1. 2030" not in text
    assert QUOTE in text.split("\n")


@pytest.mark.parametrize(
    ("day", "quote", "ok"),
    [
        (date(2026, 11, 15), "do 15. 11. 2026", True),
        (date(2026, 11, 15), "do 15.11.", True),
        (date(2026, 11, 15), "do 15.11.2026", True),
        (date(2026, 1, 15), "do 15. 11. 2026", False),
        (date(2026, 11, 5), "do 05. 11. 2026", True),
        (date(2026, 11, 15), "nejpozději 15. listopadu 2026", True),
        (date(2026, 11, 15), "Deadline: November 15, 2026", True),
        (date(2026, 11, 15), "Deadline: 15th November", True),
        (date(2026, 11, 15), "termín 2026-11-15", True),
        (date(2026, 11, 15), "do 15. 11. 2025", False),  # year mismatch
        (date(2026, 11, 15), "do 25. 11. 2026", False),
        (date(2026, 11, 15), "do 115. 11. 2026", False),
        (date(2026, 11, 15), "registrace v listopadu", False),
    ],
)
def test_date_in_quote(day: date, quote: str, ok: bool) -> None:
    assert date_in_quote(day, quote) is ok


def test_verify_accepts_backed_claim_as_prague_end_of_day() -> None:
    deadline = verify(_answer(), page_text(PAGE), NOW)
    assert deadline == datetime(2026, 11, 15, 22, 59, tzinfo=UTC)  # 23:59 CET


@pytest.mark.parametrize(
    "answer",
    [
        _answer(quote="Registrace je otevřena do 15. 11. 2026."),  # paraphrase, not on page
        _answer(day=date(2026, 12, 15)),  # date not in the quote
        _answer(day=None),
        _answer(quote=None),
    ],
)
def test_verify_rejects_unbacked_claims(answer: DeadlineExtraction) -> None:
    assert verify(answer, page_text(PAGE), NOW) is None


def test_verify_rejects_past_and_implausibly_far_dates() -> None:
    final = _answer(day=date(2027, 2, 20), quote="Finále se koná 20. 2. 2027.")
    assert verify(final, page_text(PAGE), datetime(2027, 3, 1, tzinfo=UTC)) is None  # past
    assert verify(final, page_text(PAGE), datetime(2025, 1, 1, tzinfo=UTC)) is None  # > 550 days


def test_llm_excerpt_keeps_date_lines_of_long_pages() -> None:
    filler = "\n".join(f"Odstavec bez data číslo {'x' * 50}" for _ in range(400))
    text = f"{filler}\n{QUOTE}\n{filler}"
    excerpt = llm_excerpt(text)
    assert QUOTE in excerpt
    assert len(excerpt) < 1000


# --- watcher ---------------------------------------------------------------------------


def test_verified_deadline_is_stored_and_exposed(session: Session, client: TestClient) -> None:
    _seed(session)
    llm = FakeLLM(_answer())
    report = watch_deadlines(session, llm, _pages(PAGE), NOW)
    assert (report.checked, report.extracted) == (1, 1)

    row = _row(session)
    assert row.deadline_source == "extracted"
    assert row.deadline_quote == QUOTE
    assert row.deadline_checked_at == NOW

    [out] = client.get("/opportunities").json()
    assert out["deadline"]["kind"] == "official"
    assert out["deadline"]["quote"] == QUOTE
    assert out["deadline"]["quote_url"] == WATCH


def test_hallucinated_quote_keeps_deadline_unknown(session: Session) -> None:
    _seed(session)
    report = watch_deadlines(
        session, FakeLLM(_answer(quote="Uzávěrka 15. 11. 2026")), _pages(PAGE), NOW
    )
    assert report.rejected == 1
    row = _row(session)
    assert row.deadline_at is None and row.deadline_source is None
    assert row.watch_hash is not None  # checked; same page will not be sent again


def test_unchanged_page_skips_llm(session: Session) -> None:
    _seed(session)
    watch_deadlines(session, FakeLLM(_answer()), _pages(PAGE), NOW)
    again = FakeLLM(_answer())
    report = watch_deadlines(session, again, _pages(PAGE), NOW)
    assert again.calls == 0 and report.unchanged == 1


def test_provider_down_leaves_row_untouched(session: Session) -> None:
    _seed(session)
    report = watch_deadlines(
        session, FakeLLM(ProviderError("connection refused")), _pages(PAGE), NOW
    )
    assert report.failed == 1 and "connection refused" in report.errors[0]
    row = _row(session)
    assert row.watch_hash is None and row.deadline_at is None  # retried next run


def test_page_down_is_reported(session: Session) -> None:
    _seed(session)
    report = watch_deadlines(session, FakeLLM(_answer()), _pages(None), NOW)
    assert report.failed == 1


def test_source_deadline_is_not_watched(session: Session) -> None:
    _seed(session, deadline_at=datetime(2026, 10, 30, tzinfo=UTC))
    llm = FakeLLM(_answer())
    report = watch_deadlines(session, llm, _pages(PAGE), NOW)
    assert report.checked == 0 and llm.calls == 0


def test_curated_refresh_keeps_extracted_deadline(session: Session) -> None:
    _seed(session)
    watch_deadlines(session, FakeLLM(_answer()), _pages(PAGE), NOW)
    _seed(session, description="upraveno")  # curated still says deadline_at: null
    row = _row(session)
    assert row.deadline_source == "extracted" and row.deadline_quote == QUOTE
    assert row.deadline_at == datetime(2026, 11, 15, 22, 59, tzinfo=UTC)

    _seed(session, deadline_at=datetime(2026, 11, 20, tzinfo=UTC))  # curator publishes → wins
    row = _row(session)
    assert row.deadline_source == "source" and row.deadline_quote is None


def test_stale_quote_is_withdrawn(session: Session) -> None:
    _seed(session)
    watch_deadlines(session, FakeLLM(_answer()), _pages(PAGE), NOW)
    new_page = PAGE.replace(
        "Registrace do domácího kola je otevřena do&nbsp;15.&nbsp;11.&nbsp;2026 včetně.",
        "Registrace bude brzy.",
    )
    watch_deadlines(session, FakeLLM(_answer(day=None, quote=None)), _pages(new_page), NOW)
    row = _row(session)
    assert row.deadline_at is None and row.deadline_source is None and row.deadline_quote is None


def test_runner_records_watch_status(session: Session, client: TestClient) -> None:
    _seed(session)
    report = run_sources(session, NOW, adapters=[], provider=None)
    assert report.sources[-1].source == "deadline_watch"
    assert report.sources[-1].status == "not_configured"
    statuses = {s["id"]: s for s in client.get("/sources").json()}
    assert statuses["deadline_watch"]["configured"] is False
    assert statuses["deadline_watch"]["last_status"] == "not_configured"


# --- OpenAI-compatible provider ----------------------------------------------------------


def _llm_client(answers: list[httpx.Response], seen: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"auth": request.headers.get("authorization"), **json.loads(request.content)})
        return answers.pop(0)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_provider_parses_fenced_json() -> None:
    seen: list[dict] = []
    content = '```json\n{"deadline_date": "2026-11-15", "quote": "do 15. 11. 2026"}\n```'
    client = _llm_client([_completion(content)], seen)
    provider = OpenAICompatProvider("http://127.0.0.1:20128/v1/", "oma_test", "auto/fast", client)
    result = provider.extract("text", DeadlineExtraction, "find it")
    assert result.deadline_date == date(2026, 11, 15)
    assert seen[0]["auth"] == "Bearer oma_test"
    assert seen[0]["model"] == "auto/fast" and seen[0]["temperature"] == 0


def test_provider_retries_without_response_format() -> None:
    seen: list[dict] = []
    client = _llm_client([httpx.Response(400), _completion('{"deadline_date": null}')], seen)
    provider = OpenAICompatProvider("http://x/v1", "", "m", client)
    assert provider.extract("t", DeadlineExtraction, "i").deadline_date is None
    assert "response_format" in seen[0] and "response_format" not in seen[1]
    assert seen[0]["auth"] is None


@pytest.mark.parametrize(
    "response",
    [
        _completion("no json here"),
        _completion('{"deadline_date": "not a date"}'),
        httpx.Response(500),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_provider_errors_become_provider_error(response: httpx.Response) -> None:
    provider = OpenAICompatProvider("http://x/v1", "", "m", _llm_client([response], []))
    with pytest.raises(ProviderError):
        provider.extract("t", DeadlineExtraction, "i")


def test_js_only_page_skips_llm(session: Session) -> None:
    _seed(session)
    llm = FakeLLM(_answer())
    report = watch_deadlines(
        session, llm, _pages("<html><body><div id=app></div></body></html>"), NOW
    )
    assert llm.calls == 0 and report.failed == 1 and "JS" in report.errors[0]
