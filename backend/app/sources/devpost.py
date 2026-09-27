"""Devpost hackathons (public JSON list used by devpost.com/hackathons; undocumented, fail-soft).

Keeps open, non-invite-only hackathons with an ML/AI theme that are online or in Europe.
Deadline = end of the published submission period (date only → 00:00 UTC, i.e. never later than
the real deadline). Eligibility is never read from the list, so it stays unverified.
"""

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.sources.base import Eligibility, NormalizedOpportunity, OpportunityKind

LIST_URL = "https://devpost.com/api/hackathons"
MAX_PAGES = 8
ML_THEME = "Machine Learning/AI"

EUROPE = {
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech", "czechia", "denmark",
    "estonia", "finland", "france", "germany", "greece", "hungary", "ireland", "italy",
    "latvia", "lithuania", "luxembourg", "malta", "netherlands", "norway", "poland", "portugal",
    "romania", "slovakia", "slovenia", "spain", "sweden", "switzerland", "kingdom", "uk",
    "england", "scotland", "prague", "praha", "brno", "berlin", "munich", "vienna", "london",
    "paris", "amsterdam", "zurich", "warsaw", "krakow", "bratislava", "helsinki", "espoo",
}  # fmt: skip

THEME_SIGNALS = {
    "Machine Learning/AI": ["deep_learning"],
    "Web": ["frontend", "production_backend"],
    "Mobile": ["frontend"],
    "Design": ["frontend"],
    "Databases": ["production_backend"],
    "Enterprise": ["production_backend"],
    "DevOps": ["cloud", "deployment"],
    "Serverless": ["cloud", "deployment"],
}
BASE_SIGNALS = ["hackathon_result", "teamwork", "presentation", "public_portfolio"]

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
)}  # fmt: skip
USD_RATES = {"$": 1.0, "€": 1.1, "£": 1.25}


def parse_submission_end(value: str | None) -> datetime | None:
    """'Jul 31 - Oct 01, 2026' / 'Sep 05 - 30, 2026' / 'Aug 23, 2026 - Jan 02, 2027' /
    'Sep 27, 2026' (single day) → end date; anything else → None."""
    if not value:
        return None
    start, _, end = value.strip().rpartition(" - ")
    end = end.strip()
    full = re.fullmatch(r"([A-Za-z]{3}) (\d{1,2}), (\d{4})", end)
    day_only = re.fullmatch(r"(\d{1,2}), (\d{4})", end)
    try:
        if full:
            month, day, year = MONTHS[full[1].lower()], int(full[2]), int(full[3])
        elif day_only:
            start_month = re.match(r"([A-Za-z]{3})", start)
            if not start_month:
                return None
            month, day, year = MONTHS[start_month[1].lower()], int(day_only[1]), int(day_only[2])
        else:
            return None
        return datetime(year, month, day, tzinfo=UTC)
    except (KeyError, ValueError):
        return None


def parse_prize_usd(value: str | None) -> float | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", "", value).strip()
    # Only bare $ / € / £ followed by the amount; "$CAD", "₹" etc. are unknown → None.
    match = re.fullmatch(r"([$€£])\s*([\d,]+)", text)
    if not match:
        return None
    return int(match[2].replace(",", "")) * USD_RATES[match[1]]


def _in_scope(raw: dict[str, Any]) -> bool:
    if raw.get("open_state") != "open" or raw.get("invite_only"):
        return False
    if ML_THEME not in {t.get("name") for t in raw.get("themes", [])}:
        return False
    location = (raw.get("displayed_location") or {}).get("location", "") or ""
    if location.strip().lower() == "online":
        return True
    words = set(re.split(r"[^a-z]+", location.lower()))
    return bool(words & EUROPE)


def to_opportunity(raw: dict[str, Any], now: datetime) -> NormalizedOpportunity:
    themes = [t["name"] for t in raw.get("themes", []) if t.get("name")]
    signals = [*BASE_SIGNALS, *(s for t in themes for s in THEME_SIGNALS.get(t, []))]
    prize = parse_prize_usd(raw.get("prize_amount"))
    location = (raw.get("displayed_location") or {}).get("location") or "online"
    registrations = raw.get("registrations_count")
    reason = f"Devpost hackathon, témata: {', '.join(themes)}"
    if prize:
        reason += f"; ceny ~{int(prize):,} USD".replace(",", " ")
    if registrations:
        reason += f"; {registrations} registrací"
    return NormalizedOpportunity(
        kind=OpportunityKind.HACKATHON,
        title=raw["title"].strip(),
        organizer=(raw.get("organization_name") or "Devpost").strip(),
        url=raw["url"],
        deadline_at=parse_submission_end(raw.get("submission_period_dates")),
        eligibility=Eligibility(verified=False),
        location="online" if location.lower() == "online" else location,
        signals=signals,
        cv_signal=3 if prize is not None and prize >= 10_000 else 2,
        cv_signal_reason=reason,
        source="devpost",
        source_ref=str(raw["id"]),
        evidence_url=raw["url"],
        fetched_at=now,
    )


class DevpostSource:
    id = "devpost"
    name = "Devpost hackathony"
    configured = True

    def __init__(self, client: httpx.Client | None) -> None:
        self.client = client

    def fetch(self, now: datetime) -> list[NormalizedOpportunity]:
        if self.client is None:
            raise RuntimeError("DevpostSource needs an HTTP client to fetch")
        items: dict[str, NormalizedOpportunity] = {}
        for page in range(1, MAX_PAGES + 1):
            response = self.client.get(LIST_URL, params={"status[]": "open", "page": page})
            response.raise_for_status()
            rows = response.json().get("hackathons", [])
            if not rows:
                break
            for raw in rows:
                if not _in_scope(raw):
                    continue
                item = to_opportunity(raw, now)
                if item.deadline_at is None or item.deadline_at > now:
                    items[item.source_ref] = item
        return list(items.values())
