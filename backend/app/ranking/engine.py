"""Deterministic ranking of growth actions (docs/scoring.md, ADR 0003).

Pure functions over plain facts: no database, no clock, no LLM. The same inputs always give the
same ranking, and every number that influenced it is returned for the explanation UI.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.credentials import Credential, CredentialTier, Tier, credential_tier, goal_fit
from app.opportunities.deadlines import DeadlineInfo, DeadlineKind
from app.sources.base import Eligibility
from app.taxonomy import FactorWeights, SignalCategory, Taxonomy, load_taxonomy

BENEFITS = ("relevance", "gap_coverage", "cv_signal", "skill_gain", "probability", "urgency")
PENALTIES = ("effort", "cost")

DEFAULT_WEEKLY_HOURS = 5  # used when the profile has no weekly budget
HIDING_DECISIONS = {"done", "skipped", "not_interested"}
MAX_PER_KIND = 2
MAX_AGGREGATED = 2  # Top N items from automatic sources (Devpost, Kaggle, …)
MIN_REASON_CONTRIBUTION = 0.02
# A factor must also be genuinely high to be quoted as a reason (e.g. the unknown-CV default 0.4
# or the no-deadline urgency 0.2 must never read as "strong CV signal" / "deadline is near").
MIN_REASON_FACTOR = {
    "relevance": 0.3,
    "gap_coverage": 0.2,
    "cv_signal": 0.5,
    "skill_gain": 0.3,
    "probability": 0.6,
    "urgency": 0.5,
}


class ProfileFacts(BaseModel):
    birth_date: date | None = None
    country: str | None = None
    education_level: str | None = None
    max_cost_eur: int | None = None
    weekly_hours_budget: int | None = None
    coverage: dict[str, float] = {}


class GoalFacts(BaseModel):
    required: dict[str, int]  # signal -> importance 1..3
    weights: FactorWeights


class Candidate(BaseModel):
    key: str  # "opportunity:<id>" or "action:<id>"
    source: str  # "opportunity" | "action"
    origin: str | None = None  # opportunity source adapter: "curated" | "devpost" | "kaggle"
    target_id: uuid.UUID | None = None  # row id, used to record decisions
    kind: str
    title: str
    organizer: str | None = None
    description: str | None = None
    url: str | None = None
    signals: list[str]
    cv_signal: int | None = None
    cv_signal_reason: str | None = None
    difficulty: int | None = None
    est_hours: int | None = None
    cost_eur: int | None = None
    deadline: DeadlineInfo | None = None  # None for growth actions
    eligibility: Eligibility | None = None  # None for growth actions
    credential: Credential | None = None  # certifications with curated type + issuer reputation
    closed: bool = False
    decision: str | None = None  # latest decision status
    is_new: bool = False  # first seen within the novelty window


class GapSupport(BaseModel):
    item_id: uuid.UUID | None = None
    title: str
    kind: str
    coverage: float


class GapItem(BaseModel):
    supports: list[GapSupport] = Field(default_factory=list)
    signal: str
    label: str
    importance: int
    coverage: float
    gap: float


class RankedItem(BaseModel):
    candidate: Candidate
    priority: float
    factors: dict[str, float]
    contributions: dict[str, float]
    reasons: list[str]
    warnings: list[str]
    credential_tier: CredentialTier | None = None


class FilteredItem(BaseModel):
    candidate: Candidate
    reason: str


class RankingResult(BaseModel):
    top: list[RankedItem]
    ranked: list[RankedItem]
    filtered: list[FilteredItem]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _labels(signals: list[str], taxonomy: Taxonomy) -> str:
    by_id = taxonomy.by_id
    return ", ".join(by_id[s].label if s in by_id else s for s in signals)


# --- gaps --------------------------------------------------------------------------------


def goal_gaps(goal: GoalFacts, coverage: dict[str, float], taxonomy: Taxonomy) -> list[GapItem]:
    """All required signals with their gap, biggest gap first (ties: signal id)."""
    by_id = taxonomy.by_id
    items = [
        GapItem(
            signal=signal,
            label=by_id[signal].label if signal in by_id else signal,
            importance=importance,
            coverage=coverage.get(signal, 0.0),
            gap=importance * (1 - coverage.get(signal, 0.0)),
        )
        for signal, importance in goal.required.items()
    ]
    return sorted(items, key=lambda g: (-g.gap, g.signal))


# --- gates -------------------------------------------------------------------------------


def _age_on(birth: date, day: date) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def gate(candidate: Candidate, profile: ProfileFacts, now: datetime) -> str | None:
    """Return the Czech reason the candidate is excluded, or None if it passes."""
    if candidate.closed:
        return "Už není v nabídce"
    if candidate.decision in HIDING_DECISIONS:
        return (
            "Rozhodnuto: "
            + {
                "done": "hotovo",
                "skipped": "přeskočeno",
                "not_interested": "nezajímá mě",
            }[candidate.decision]
        )
    if candidate.deadline is not None and candidate.deadline.kind == DeadlineKind.PASSED:
        return "Deadline uplynul"
    elig = candidate.eligibility
    if elig is not None:
        if profile.birth_date is not None and (elig.min_age or elig.max_age):
            when = candidate.deadline.date if candidate.deadline else None
            age = _age_on(profile.birth_date, (when or now).date())
            if elig.min_age is not None and age < elig.min_age:
                return f"Věk: minimum {elig.min_age} let"
            if elig.max_age is not None and age > elig.max_age:
                return f"Věk: maximum {elig.max_age} let"
        if (
            elig.education_levels is not None
            and profile.education_level is not None
            and profile.education_level not in elig.education_levels
        ):
            return "Nesplňuješ požadované vzdělání"
        if (
            elig.countries is not None
            and profile.country is not None
            and profile.country.upper() not in {c.upper() for c in elig.countries}
        ):
            return "Není otevřeno pro tvoji zemi"
    if (
        candidate.cost_eur is not None
        and profile.max_cost_eur is not None
        and candidate.cost_eur > profile.max_cost_eur
    ):
        return f"Cena {candidate.cost_eur} € je nad tvým limitem {profile.max_cost_eur} €"
    return None


# --- factors -----------------------------------------------------------------------------


def _urgency(deadline: DeadlineInfo | None, now: datetime) -> float:
    if deadline is None or deadline.date is None:
        return 0.2
    days = (deadline.date - now).total_seconds() / 86400
    curve = 1.0 if days <= 7 else _clamp((90 - days) / (90 - 7))
    if deadline.kind == DeadlineKind.EXPECTED:
        return curve * 0.5
    return curve


def compute_factors(
    candidate: Candidate,
    profile: ProfileFacts,
    goal: GoalFacts,
    now: datetime,
    taxonomy: Taxonomy,
) -> dict[str, float]:
    cov = profile.coverage
    signals = candidate.signals
    required = goal.required
    gaps = {s: imp * (1 - cov.get(s, 0.0)) for s, imp in required.items()}

    weight_total = sum(required.get(s, 1) for s in signals)
    on_goal = sum(required[s] for s in signals if s in required)
    relevance = on_goal / weight_total if weight_total else 0.0

    top3 = sum(sorted(gaps.values(), reverse=True)[:3])
    covered_gap = sum(gaps[s] for s in signals if s in gaps)
    gap_coverage = _clamp(covered_gap / top3) if top3 > 0 else 0.0

    cv_signal = (candidate.cv_signal - 1) / 4 if candidate.cv_signal is not None else 0.4

    by_id = taxonomy.by_id
    skill_signals = [s for s in signals if s in by_id and by_id[s].category == SignalCategory.SKILL]
    skill_gain = (
        sum(1 - cov.get(s, 0.0) for s in skill_signals) / len(skill_signals)
        if skill_signals
        else 0.0
    )

    readiness = sum(cov.get(s, 0.0) for s in signals) / len(signals) if signals else 0.0
    difficulty = candidate.difficulty if candidate.difficulty is not None else 3
    certainty = (
        0.7 if candidate.eligibility is not None and not candidate.eligibility.verified else 1.0
    )
    probability = certainty * _clamp(0.5 + 0.5 * readiness - 0.15 * (difficulty - 3), 0.1, 1.0)

    budget = profile.weekly_hours_budget or DEFAULT_WEEKLY_HOURS
    effort = _clamp(candidate.est_hours / (4 * budget)) if candidate.est_hours is not None else 0.3

    if candidate.cost_eur is None:
        cost = 0.2
    elif candidate.cost_eur == 0:
        cost = 0.0
    else:
        cost = _clamp(candidate.cost_eur / (profile.max_cost_eur or 200))

    return {
        "relevance": relevance,
        "gap_coverage": gap_coverage,
        "cv_signal": cv_signal,
        "skill_gain": skill_gain,
        "probability": probability,
        "urgency": _urgency(candidate.deadline, now),
        "effort": effort,
        "cost": cost,
    }


def contributions(factors: dict[str, float], weights: FactorWeights) -> dict[str, float]:
    w = weights.model_dump()
    result = {name: w[name] * factors[name] for name in BENEFITS}
    result.update({name: -w[name] * factors[name] for name in PENALTIES})
    return result


# --- explanations ------------------------------------------------------------------------


def _reason(
    name: str, candidate: Candidate, profile: ProfileFacts, goal: GoalFacts, taxonomy: Taxonomy
) -> str:
    cov = profile.coverage
    signals = candidate.signals
    if name == "relevance":
        on_goal = [s for s in signals if s in goal.required]
        return f"Sedí k cíli: {_labels(on_goal, taxonomy)}"
    if name == "gap_coverage":
        gapped = sorted(
            (s for s in signals if s in goal.required and cov.get(s, 0.0) < 1),
            key=lambda s: (-goal.required[s] * (1 - cov.get(s, 0.0)), s),
        )
        return f"Pokrývá tvoje mezery: {_labels(gapped[:3], taxonomy)}"
    if name == "cv_signal":
        if candidate.cv_signal_reason:
            return f"Silný signál do CV — {candidate.cv_signal_reason}"
        return "Silný signál do CV"
    if name == "skill_gain":
        new = [s for s in signals if cov.get(s, 0.0) < 0.5 and s in taxonomy.by_id]
        new = [s for s in new if taxonomy.by_id[s].category == SignalCategory.SKILL]
        return f"Naučíš se: {_labels(new[:3], taxonomy)}" if new else "Posune tvoje dovednosti"
    if name == "probability":
        return "Máš dobrou šanci uspět"
    if name == "urgency" and candidate.deadline is not None:
        return f"Termín se blíží: {candidate.deadline.label}"
    return "Časově vhodné"


def _warnings(candidate: Candidate, profile: ProfileFacts) -> list[str]:
    warnings: list[str] = []
    if candidate.eligibility is not None and not candidate.eligibility.verified:
        warnings.append("Podmínky účasti nejsou ověřené — zkontroluj pravidla")
    if candidate.deadline is not None:
        if candidate.deadline.kind == DeadlineKind.EXPECTED:
            warnings.append("Termín je jen odhad podle minulého ročníku")
        elif candidate.deadline.kind == DeadlineKind.UNKNOWN:
            warnings.append("Deadline zatím nezveřejněn")
    if candidate.cost_eur:
        warnings.append(f"Placené: {candidate.cost_eur} €")
    elif candidate.cost_eur is None and candidate.source == "opportunity":
        warnings.append("Cena neuvedena")
    budget = profile.weekly_hours_budget or DEFAULT_WEEKLY_HOURS
    if candidate.est_hours is not None and candidate.est_hours > 4 * budget:
        warnings.append(f"Časově náročné: ~{candidate.est_hours} h")
    return warnings


# --- ranking -----------------------------------------------------------------------------


def score(
    candidate: Candidate,
    profile: ProfileFacts,
    goal: GoalFacts,
    now: datetime,
    taxonomy: Taxonomy,
) -> RankedItem:
    factors = compute_factors(candidate, profile, goal, now, taxonomy)
    contrib = contributions(factors, goal.weights)
    tier = None
    if candidate.credential is not None:
        fit = goal_fit(factors["relevance"], factors["gap_coverage"])
        tier = credential_tier(candidate.credential, fit)
        # Credential reputation contributes only to the outward CV signal.
        # The learning factor remains independent even for a weak badge.
        factors["cv_signal"] = min(factors["cv_signal"], tier.score)
        contrib = contributions(factors, goal.weights)
    positive = sorted(
        (
            (name, value)
            for name, value in contrib.items()
            if value >= MIN_REASON_CONTRIBUTION and factors[name] >= MIN_REASON_FACTOR[name]
        ),
        key=lambda nv: (-nv[1], nv[0]),
    )
    return RankedItem(
        candidate=candidate,
        priority=round(sum(contrib.values()), 6),
        factors={k: round(v, 4) for k, v in factors.items()},
        contributions={k: round(v, 4) for k, v in contrib.items()},
        reasons=[_reason(name, candidate, profile, goal, taxonomy) for name, _ in positive[:3]],
        warnings=_warnings(candidate, profile),
        credential_tier=tier,
    )


def _sort_key(item: RankedItem) -> tuple[float, float, str, str]:
    deadline = item.candidate.deadline
    when = deadline.date.timestamp() if deadline and deadline.date else float("inf")
    return (-item.priority, when, item.candidate.title, item.candidate.key)


def diversify(
    ranked: list[RankedItem], n: int, max_per_kind: int = MAX_PER_KIND
) -> list[RankedItem]:
    """Greedy Top N with at most ``max_per_kind`` of one kind and ``MAX_AGGREGATED`` items from
    automatic sources, so near-identical feed items cannot crowd out curated ones; backfills if
    the list runs short."""
    top: list[RankedItem] = []
    per_kind: dict[str, int] = {}
    aggregated = 0
    for item in ranked:
        if len(top) == n:
            break
        is_aggregated = item.candidate.origin not in (None, "curated")
        if per_kind.get(item.candidate.kind, 0) < max_per_kind and not (
            is_aggregated and aggregated >= MAX_AGGREGATED
        ):
            top.append(item)
            per_kind[item.candidate.kind] = per_kind.get(item.candidate.kind, 0) + 1
            aggregated += is_aggregated
    if len(top) < n:
        chosen = {item.candidate.key for item in top}
        top += [item for item in ranked if item.candidate.key not in chosen][: n - len(top)]
        top.sort(key=_sort_key)
    return top


def rank(
    candidates: list[Candidate],
    profile: ProfileFacts,
    goal: GoalFacts,
    now: datetime,
    top_n: int = 5,
    taxonomy: Taxonomy | None = None,
) -> RankingResult:
    taxonomy = taxonomy or load_taxonomy()
    ranked: list[RankedItem] = []
    filtered: list[FilteredItem] = []
    for candidate in candidates:
        reason = gate(candidate, profile, now)
        if reason is not None:
            filtered.append(FilteredItem(candidate=candidate, reason=reason))
            continue
        item = score(candidate, profile, goal, now, taxonomy)
        if item.credential_tier is not None and item.credential_tier.tier == Tier.IGNORE:
            item.warnings.append("Slabý certifikát; přínos učení se hodnotí samostatně.")
        ranked.append(item)
    ranked.sort(key=_sort_key)
    filtered.sort(key=lambda f: (f.candidate.title, f.candidate.key))
    return RankingResult(top=diversify(ranked, top_n), ranked=ranked, filtered=filtered)
