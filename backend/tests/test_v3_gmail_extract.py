from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.ai.provider import ProviderError
from app.config import Settings
from app.gmail.client import MailMessage
from app.gmail.extract import (
    UNKNOWN_ORGANIZER,
    MailAchievement,
    MailExtraction,
    MailOpportunity,
    process_gmail,
)
from app.gmail.models import GmailMessage
from app.growth.models import ImportProposal
from app.opportunities.models import Opportunity

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
SETTINGS = Settings(gmail_label="growthOS", gmail_max_messages=10)

BODY = """Subject: Pozvánka na AI Hackathon Brno
Ahoj, Czech AI Society pořádá AI Hackathon Brno.
Registrace je otevřená do 15. 11. 2026 na https://example.org/hack/ včetně týmů.
Gratulujeme, v soutěži Datathon 2026 jste získali 2. místo (vyhlášeno 10. 5. 2026).
Minulý ročník Robotiády měl uzávěrku 1. 3. 2026."""


def message(message_id: str = "m1", text: str = BODY) -> MailMessage:
    return MailMessage(message_id, "Pozvánka", NOW, text)


class FakeGmail:
    def __init__(self, messages: list[MailMessage], label: str | None = "L1"):
        self.messages = {m.id: m for m in messages}
        self.label = label
        self.fetched: list[str] = []

    def label_id(self, name):
        return self.label

    def message_ids(self, label_id, limit):
        assert label_id == "L1"
        return list(self.messages)[:limit]

    def message(self, message_id):
        self.fetched.append(message_id)
        return self.messages[message_id]


class FakeLLM:
    name = "fake"

    def __init__(self, answer: MailExtraction | None = None, error: bool = False):
        self.answer, self.error, self.calls = answer, error, 0

    def extract(self, text, schema, instructions):
        self.calls += 1
        if self.error:
            raise ProviderError("down")
        return self.answer


def good_answer() -> MailExtraction:
    return MailExtraction(
        opportunities=[
            MailOpportunity(
                title="AI Hackathon Brno",
                kind="hackathon",
                organizer="Czech AI Society",
                url="https://example.org/hack",
                deadline_date=date(2026, 11, 15),
                quote="Registrace je otevřená do 15. 11. 2026 na https://example.org/hack/",
            )
        ],
        achievements=[
            MailAchievement(
                title="Datathon 2026",
                result="2. místo",
                achieved_on=date(2026, 5, 10),
                quote="v soutěži Datathon 2026 jste získali 2. místo (vyhlášeno 10. 5. 2026).",
            )
        ],
    )


def test_verified_items_are_stored(session):
    report = process_gmail(session, FakeLLM(good_answer()), FakeGmail([message()]), SETTINGS, NOW)
    assert (report.opportunities, report.proposals, report.rejected) == (1, 1, 0)
    row = session.scalars(select(Opportunity).where(Opportunity.source == "gmail")).one()
    assert row.url == "https://example.org/hack" and row.organizer == "Czech AI Society"
    assert row.deadline_source == "extracted" and row.deadline_at.date() == date(2026, 11, 15)
    assert row.evidence_url.endswith("#all/m1") and row.eligibility["verified"] is False
    proposal = session.scalars(select(ImportProposal)).one()
    assert proposal.source == "gmail" and proposal.proposed["result"] == "2. místo"
    assert proposal.proposed["achieved_on"] == "2026-05-10"
    assert proposal.excerpt.startswith("v soutěži Datathon")


def test_hallucinations_are_dropped(session):
    answer = MailExtraction(
        opportunities=[
            MailOpportunity(title="Invented", kind="hackathon", quote="Přihlas se do zítřka!"),
            MailOpportunity(title="Wrong kind", kind="party", quote="AI Hackathon Brno."),
            MailOpportunity(  # past deadline written in the mail → nothing to apply to
                title="Robotiáda",
                kind="competition",
                deadline_date=date(2026, 3, 1),
                quote="Minulý ročník Robotiády měl uzávěrku 1. 3. 2026.",
            ),
            MailOpportunity(  # date not in quote, organizer/url not in mail → fields dropped
                title="AI Hackathon Brno",
                kind="hackathon",
                organizer="Google",
                url="https://evil.example/",
                deadline_date=date(2026, 12, 1),
                quote="Czech AI Society pořádá AI Hackathon Brno.",
            ),
        ],
        achievements=[
            MailAchievement(title="Olympiáda", result="1. místo", quote="Vyhrál jsi olympiádu."),
            MailAchievement(
                title="Datathon",
                result="1. místo",
                achieved_on=date(2026, 5, 11),
                quote="jste získali 2. místo (vyhlášeno 10. 5. 2026)",
            ),
        ],
    )
    report = process_gmail(session, FakeLLM(answer), FakeGmail([message()]), SETTINGS, NOW)
    assert report.rejected == 4 and report.opportunities == 1 and report.proposals == 1
    row = session.scalars(select(Opportunity)).one()
    assert row.deadline_at is None and row.organizer == UNKNOWN_ORGANIZER
    assert row.url.endswith("#all/m1")
    proposed = session.scalars(select(ImportProposal)).one().proposed
    assert proposed["result"] is None and proposed["achieved_on"] is None


def test_processed_messages_are_not_sent_again(session):
    gmail, llm = FakeGmail([message()]), FakeLLM(good_answer())
    process_gmail(session, llm, gmail, SETTINGS, NOW)
    report = process_gmail(session, llm, gmail, SETTINGS, NOW)
    assert llm.calls == 1 and gmail.fetched == ["m1"] and report.checked == 0
    assert session.get(GmailMessage, "m1").found == 2


def test_provider_down_is_retried(session):
    gmail = FakeGmail([message()])
    report = process_gmail(session, FakeLLM(error=True), gmail, SETTINGS, NOW)
    assert report.failed == 1 and session.get(GmailMessage, "m1") is None
    report = process_gmail(session, FakeLLM(good_answer()), gmail, SETTINGS, NOW)
    assert report.opportunities == 1


def test_short_mail_skips_llm(session):
    llm = FakeLLM(good_answer())
    process_gmail(session, llm, FakeGmail([message(text="Subject: hi")]), SETTINGS, NOW)
    assert llm.calls == 0 and session.get(GmailMessage, "m1").status == "empty"


def test_missing_label_is_an_error(session):
    with pytest.raises(HTTPException) as err:
        process_gmail(session, FakeLLM(), FakeGmail([], label=None), SETTINGS, NOW)
    assert "growthOS" in err.value.detail


def test_known_opportunity_gets_the_deadline(session):
    from app.opportunities.service import upsert_opportunities
    from app.sources.base import NormalizedOpportunity

    known = NormalizedOpportunity(
        kind="hackathon",
        title="AI Hackathon Brno",
        organizer="Czech AI Society",
        url="https://example.org/hack/",
        source="curated",
        source_ref="hack",
        evidence_url="https://example.org/hack/",
        fetched_at=NOW,
    )
    upsert_opportunities(session, "curated", [known])
    answer = good_answer()
    answer.achievements = []
    report = process_gmail(session, FakeLLM(answer), FakeGmail([message()]), SETTINGS, NOW)
    assert report.deadlines == 1 and report.opportunities == 0
    row = session.scalars(select(Opportunity)).one()
    assert row.source == "curated" and row.deadline_source == "extracted"
    assert "15. 11. 2026" in row.deadline_quote


def test_sources_list_gmail_as_not_configured(client):
    rows = {row["id"]: row for row in client.get("/sources").json()}
    assert rows["gmail"]["configured"] is False and rows["gmail"]["enabled"] is False
