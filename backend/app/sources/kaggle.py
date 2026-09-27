"""Kaggle competitions (official API v1, needs KAGGLE_USERNAME + KAGGLE_KEY from kaggle.json).

Deadlines come from the API, so they are official. Eligibility (age, country) differs per
competition and is not in the list → unverified.
"""

from datetime import datetime
from typing import Any

import httpx
from pydantic import AwareDatetime, TypeAdapter, ValidationError

from app.sources.base import Eligibility, NormalizedOpportunity, OpportunityKind

LIST_URL = "https://www.kaggle.com/api/v1/competitions/list"
MAX_PAGES = 5

CATEGORY_CV_SIGNAL = {
    "featured": 4,
    "research": 4,
    "recruitment": 3,
    "playground": 2,
    "analytics": 2,
    "getting started": 1,
    "gettingstarted": 1,
    "community": 1,
}
TAG_SIGNALS = {
    "tabular": ["classical_ml"],
    "tabular data": ["classical_ml"],
    "regression": ["classical_ml"],
    "classification": ["classical_ml"],
    "image": ["computer_vision", "deep_learning"],
    "computer vision": ["computer_vision", "deep_learning"],
    "video": ["computer_vision", "deep_learning"],
    "text": ["nlp", "deep_learning"],
    "nlp": ["nlp", "deep_learning"],
    "natural language processing": ["nlp", "deep_learning"],
    "text generation": ["nlp", "deep_learning"],
    "audio": ["deep_learning"],
    "deep learning": ["deep_learning"],
    "time series analysis": ["classical_ml", "data_analysis"],
    "data analytics": ["data_analysis"],
    "reinforcement learning": ["deep_learning"],
}
BASE_SIGNALS = ["ml_competition_result", "python", "public_portfolio"]

_deadline = TypeAdapter(AwareDatetime)


def _get(raw: dict[str, Any], *names: str) -> Any:
    for name in names:
        if raw.get(name) not in (None, ""):
            return raw[name]
    return None


def _category(raw: dict[str, Any]) -> str:
    return str(_get(raw, "category") or "").strip().lower()


def _parse_deadline(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _deadline.validate_python(text)
    except ValidationError:
        return None  # naive or garbage → treat as not published


def _url(raw: dict[str, Any]) -> str:
    ref = str(_get(raw, "url", "ref") or "")
    if ref.startswith("http"):
        return ref
    return f"https://www.kaggle.com/competitions/{ref.strip('/').split('/')[-1]}"


def to_opportunity(raw: dict[str, Any], now: datetime) -> NormalizedOpportunity:
    tags = [str(t.get("name") or t.get("ref") or "").lower() for t in raw.get("tags") or []]
    signals = [*BASE_SIGNALS, *(s for t in tags for s in TAG_SIGNALS.get(t, []))]
    category = _category(raw)
    reward = _get(raw, "reward")
    teams = _get(raw, "teamCount", "team_count")
    reason = f"Kaggle soutěž ({category or 'neznámá kategorie'})"
    if reward:
        reason += f"; odměna: {reward}"
    if teams:
        reason += f"; {teams} týmů"
    url = _url(raw)
    return NormalizedOpportunity(
        kind=OpportunityKind.COMPETITION,
        title=str(raw["title"]).strip(),
        organizer=str(_get(raw, "organizationName", "organization_name") or "Kaggle").strip(),
        url=url,
        description=_get(raw, "description"),
        deadline_at=_parse_deadline(_get(raw, "deadline")),
        eligibility=Eligibility(verified=False),
        cost_eur=0,  # entering a Kaggle competition is free
        location="online",
        signals=signals,
        cv_signal=CATEGORY_CV_SIGNAL.get(category, 2),
        cv_signal_reason=reason,
        source="kaggle",
        source_ref=str(_get(raw, "id") or url),
        evidence_url=url,
        fetched_at=now,
    )


class KaggleSource:
    id = "kaggle"
    name = "Kaggle soutěže"

    def __init__(self, client: httpx.Client | None, username: str, key: str) -> None:
        self.client = client
        self.username = username.strip()
        self.key = key.strip()

    @property
    def configured(self) -> bool:
        return bool(self.username and self.key)

    def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
        if self.client is None:
            raise RuntimeError("KaggleSource needs an HTTP client to fetch")
        items: dict[str, NormalizedOpportunity] = {}
        for page in range(1, MAX_PAGES + 1):
            response = self.client.get(
                LIST_URL,
                params={"page": page, "category": "all", "sortBy": "latestDeadline"},
                auth=(self.username, self.key),
            )
            response.raise_for_status()
            body = response.json()
            rows = body.get("competitions", []) if isinstance(body, dict) else body
            if not rows:
                break
            for raw in rows:
                item = to_opportunity(raw, now)
                # an active competition always has a deadline; without one we cannot tell
                if item.deadline_at is not None and item.deadline_at > now:
                    items[item.source_ref] = item
        return list(items.values())
