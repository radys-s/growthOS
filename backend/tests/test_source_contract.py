from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.sources.base import NormalizedOpportunity, OpportunityKind, SourceAdapter

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def make(**overrides: object) -> NormalizedOpportunity:
    data: dict[str, object] = {
        "kind": OpportunityKind.OLYMPIAD,
        "title": "Mezinárodní Olympiáda AI",
        "organizer": "IOAI",
        "url": "https://ioai-official.org",
        "deadline_at": datetime(2027, 3, 1, 23, 59, tzinfo=UTC),
        "source": "curated",
        "source_ref": "ioai-2027",
        "evidence_url": "https://ioai-official.org",
        "fetched_at": NOW,
    }
    data.update(overrides)
    return NormalizedOpportunity.model_validate(data)


def test_dedup_key_is_normalized() -> None:
    assert make().dedup_key == "mezinarodni-olympiada-ai|ioai|2027-03-01"


def test_missing_deadline_is_explicit_none() -> None:
    assert make(deadline_at=None).dedup_key.endswith("|none")


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make(deadline_at=datetime(2027, 3, 1))


def test_adapter_protocol_is_structural() -> None:
    class FakeAdapter:
        id = "fake"
        name = "Fake"

        def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
            return [make(fetched_at=now)]

    adapter = FakeAdapter()
    assert isinstance(adapter, SourceAdapter)
    assert adapter.fetch(NOW)[0].source == "curated"
