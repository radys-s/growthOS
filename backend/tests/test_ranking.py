from datetime import UTC, date, datetime, timedelta

import pytest

from app.opportunities.deadlines import DeadlineInfo, DeadlineKind
from app.ranking.engine import (
    Candidate,
    GoalFacts,
    ProfileFacts,
    compute_factors,
    diversify,
    gate,
    goal_gaps,
    rank,
    score,
)
from app.sources.base import Eligibility
from app.taxonomy import FactorWeights, load_taxonomy

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
TAX = load_taxonomy()
WEIGHTS = FactorWeights(
    relevance=0.2,
    gap_coverage=0.3,
    cv_signal=0.2,
    skill_gain=0.1,
    probability=0.1,
    urgency=0.1,
    effort=0.15,
    cost=0.1,
)
GOAL = GoalFacts(
    required={"deployment": 3, "deep_learning": 3, "research_evidence": 2, "teamwork": 1},
    weights=WEIGHTS,
)
PROFILE = ProfileFacts(
    birth_date=date(2009, 5, 1),
    country="CZ",
    education_level="high_school",
    max_cost_eur=100,
    weekly_hours_budget=10,
    coverage={"deep_learning": 0.75, "python": 1.0},
)


def _cand(key: str = "a", **extra) -> Candidate:
    base = {
        "key": key,
        "source": "action",
        "kind": "build",
        "title": key.upper(),
        "signals": ["deployment"],
    }
    return Candidate.model_validate({**base, **extra})


def _deadline(days: float, kind: DeadlineKind = DeadlineKind.OFFICIAL) -> DeadlineInfo:
    return DeadlineInfo(kind=kind, date=NOW + timedelta(days=days), label="x")


# --- gaps -------------------------------------------------------------------------------


def test_goal_gaps_sorted_by_gap() -> None:
    gaps = goal_gaps(GOAL, PROFILE.coverage, TAX)
    assert [g.signal for g in gaps] == [
        "deployment",
        "research_evidence",
        "teamwork",
        "deep_learning",
    ]
    assert gaps[0].gap == 3 and gaps[3].gap == pytest.approx(0.75)


# --- gates ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({"closed": True}, "Už není v nabídce"),
        ({"decision": "done"}, "Rozhodnuto: hotovo"),
        ({"decision": "not_interested"}, "Rozhodnuto: nezajímá mě"),
        ({"deadline": {"kind": "passed", "date": NOW, "label": "x"}}, "Deadline uplynul"),
        ({"eligibility": {"max_age": 16}}, "Věk: maximum 16 let"),
        ({"eligibility": {"min_age": 18}}, "Věk: minimum 18 let"),
        ({"eligibility": {"education_levels": ["bachelor"]}}, "Nesplňuješ požadované vzdělání"),
        ({"eligibility": {"countries": ["US"]}}, "Není otevřeno pro tvoji zemi"),
        ({"cost_eur": 150}, "Cena 150 € je nad tvým limitem 100 €"),
    ],
)
def test_gates_exclude(extra: dict, expected: str) -> None:
    assert gate(_cand(**extra), PROFILE, NOW) == expected


def test_gates_pass_unknowns() -> None:
    unknown = ProfileFacts()
    candidate = _cand(eligibility={"max_age": 16, "countries": ["US"]}, cost_eur=500)
    assert gate(candidate, unknown, NOW) is None
    assert gate(_cand(decision="planned"), PROFILE, NOW) is None
    assert gate(_cand(decision="already_knew"), PROFILE, NOW) is None


def test_age_gate_uses_deadline_date() -> None:
    # Turns 18 on 1 May 2027; a deadline after that must pass min_age=18.
    deadline = {"kind": "official", "date": datetime(2027, 6, 1, tzinfo=UTC), "label": "x"}
    assert gate(_cand(eligibility={"min_age": 18}, deadline=deadline), PROFILE, NOW) is None


# --- factors ----------------------------------------------------------------------------


def test_relevance_and_gap_coverage() -> None:
    f = compute_factors(_cand(signals=["deployment", "python"]), PROFILE, GOAL, NOW, TAX)
    assert f["relevance"] == pytest.approx(3 / 4)  # deployment 3 of (3 + 1 off-goal)
    top3 = 3 + 2 + 1  # deployment, research_evidence, teamwork
    assert f["gap_coverage"] == pytest.approx(3 / top3)


def test_no_signals_and_defaults() -> None:
    f = compute_factors(_cand(signals=[]), PROFILE, GOAL, NOW, TAX)
    assert f["relevance"] == 0 and f["gap_coverage"] == 0 and f["skill_gain"] == 0
    assert f["cv_signal"] == 0.4 and f["effort"] == 0.3 and f["cost"] == 0.2
    assert f["urgency"] == 0.2  # no deadline
    assert f["probability"] == pytest.approx(0.5)  # readiness 0, difficulty 3, certain


def test_skill_gain_only_counts_skills() -> None:
    f = compute_factors(
        _cand(signals=["deep_learning", "research_evidence"]), PROFILE, GOAL, NOW, TAX
    )
    assert f["skill_gain"] == pytest.approx(0.25)


def test_probability_certainty_and_difficulty() -> None:
    verified = compute_factors(
        _cand(eligibility={"verified": True}, difficulty=5), PROFILE, GOAL, NOW, TAX
    )
    unverified = compute_factors(
        _cand(eligibility={"verified": False}, difficulty=5), PROFILE, GOAL, NOW, TAX
    )
    assert verified["probability"] == pytest.approx(0.2)
    assert unverified["probability"] == pytest.approx(0.7 * 0.2)


@pytest.mark.parametrize(
    ("days", "kind", "expected"),
    [
        (3, DeadlineKind.OFFICIAL, 1.0),
        (7, DeadlineKind.OFFICIAL, 1.0),
        (48.5, DeadlineKind.OFFICIAL, 0.5),
        (120, DeadlineKind.OFFICIAL, 0.0),
        (3, DeadlineKind.EXPECTED, 0.5),
    ],
)
def test_urgency_curve(days: float, kind: DeadlineKind, expected: float) -> None:
    f = compute_factors(_cand(deadline=_deadline(days, kind)), PROFILE, GOAL, NOW, TAX)
    assert f["urgency"] == pytest.approx(expected)


def test_effort_and_cost_penalties() -> None:
    f = compute_factors(_cand(est_hours=20, cost_eur=50), PROFILE, GOAL, NOW, TAX)
    assert f["effort"] == pytest.approx(0.5)  # 20 / (4 * 10)
    assert f["cost"] == pytest.approx(0.5)  # 50 / 100
    free = compute_factors(_cand(est_hours=400, cost_eur=0), PROFILE, GOAL, NOW, TAX)
    assert free["effort"] == 1 and free["cost"] == 0


# --- priority + explanations -----------------------------------------------------------


def test_priority_is_sum_of_contributions() -> None:
    item = score(_cand(cv_signal=5, est_hours=10, cost_eur=0), PROFILE, GOAL, NOW, TAX)
    assert item.priority == pytest.approx(sum(item.contributions.values()), abs=1e-3)
    assert item.contributions["effort"] < 0
    # cv 0.2 ties relevance 0.2 (broken by name), then gap 0.3 × 0.5 = 0.15.
    assert item.reasons == [
        "Silný signál do CV",
        "Sedí k cíli: Nasazení modelů / aplikací",
        "Pokrývá tvoje mezery: Nasazení modelů / aplikací",
    ]


def test_reasons_and_warnings() -> None:
    candidate = _cand(
        source="opportunity",
        kind="competition",
        signals=["deployment", "research_evidence"],
        cv_signal=5,
        cv_signal_reason="mezinárodní uznání",
        eligibility={"verified": False},
        deadline={"kind": "expected", "date": NOW + timedelta(days=100), "label": "~březen"},
    )
    item = score(candidate, PROFILE, GOAL, NOW, TAX)
    assert len(item.reasons) <= 3
    assert any(r.startswith("Pokrývá tvoje mezery") for r in item.reasons)
    assert any("mezinárodní uznání" in r for r in item.reasons)
    assert "Podmínky účasti nejsou ověřené — zkontroluj pravidla" in item.warnings
    assert "Termín je jen odhad podle minulého ročníku" in item.warnings
    assert "Cena neuvedena" in item.warnings


def test_rank_is_deterministic_and_orders() -> None:
    strong = _cand("strong", signals=["deployment", "research_evidence"], cv_signal=5)
    weak = _cand("weak", signals=["python"], cv_signal=1)
    hidden = _cand("hidden", decision="skipped")
    first = rank([weak, hidden, strong], PROFILE, GOAL, NOW)
    second = rank([strong, weak, hidden], PROFILE, GOAL, NOW)
    assert first == second
    assert [i.candidate.key for i in first.ranked] == ["strong", "weak"]
    assert [f.candidate.key for f in first.filtered] == ["hidden"]


def test_tie_break_by_deadline_then_title() -> None:
    later = _cand("b", deadline=_deadline(200))
    sooner = _cand("c", deadline=_deadline(150))
    none = _cand("a")
    # Urgency is 0 for both deadlines ≥ 90 days, but 0.2 without one — give same weight 0.
    goal = GOAL.model_copy(update={"weights": WEIGHTS.model_copy(update={"urgency": 0})})
    result = rank([none, later, sooner], PROFILE, goal, NOW)
    assert [i.candidate.key for i in result.ranked] == ["c", "b", "a"]


# --- diversity ----------------------------------------------------------------------------


def test_diversity_max_two_per_kind_and_backfill() -> None:
    items = [
        score(_cand(f"b{i}", kind="build", cv_signal=5), PROFILE, GOAL, NOW, TAX) for i in range(4)
    ] + [score(_cand("l1", kind="learn", cv_signal=1), PROFILE, GOAL, NOW, TAX)]
    items.sort(key=lambda i: -i.priority)
    top = diversify(items, 3)
    assert [i.candidate.kind for i in top].count("build") == 2
    assert "l1" in {i.candidate.key for i in top}
    # Only builds available beyond the cap → backfill so the list is not short.
    assert len(diversify(items, 5)) == 5


def test_top_n_limit() -> None:
    candidates = [_cand(f"k{i}", kind=f"kind{i}") for i in range(8)]
    assert len(rank(candidates, PROFILE, GOAL, NOW, top_n=5).top) == 5


def test_eligibility_model_used_in_candidate() -> None:
    assert isinstance(_cand(eligibility={}).eligibility, Eligibility)


def test_weak_factors_are_not_quoted_as_reasons() -> None:
    # Unknown CV (0.4), no deadline (0.2), low probability: none may become a reason.
    item = score(_cand(signals=["teamwork"], difficulty=5), PROFILE, GOAL, NOW, TAX)
    assert not any(r.startswith(("Silný signál", "Termín", "Máš dobrou")) for r in item.reasons)


# --- credential tiers ---------------------------------------------------------------------


def test_credential_value_does_not_gate_learning() -> None:
    on_goal = _cand(
        "cert",
        kind="certification",
        signals=["deployment"],
        credential={"type": "industry_certification", "issuer_reputation": 5},
    )
    off_goal = _cand(
        "badge",
        kind="certification",
        signals=["python"],
        credential={"type": "participation_badge", "issuer_reputation": 2},
    )
    plain = _cand("plain")
    result = rank([on_goal, off_goal, plain], PROFILE, GOAL, NOW)

    by_key = {i.candidate.key: i for i in result.ranked}
    assert by_key["cert"].credential_tier is not None
    assert by_key["cert"].credential_tier.tier == "S"  # deployment: on goal, uncovered gap
    assert by_key["plain"].credential_tier is None
    assert not result.filtered
    assert by_key["badge"].credential_tier.tier == "ignore"
    assert by_key["badge"].warnings
