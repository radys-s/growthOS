# Scoring & ranking spec (M1)

Deterministic and explainable (ADR 0003). Implementation: `backend/app/ranking/`.
Inputs are stored facts; the same inputs always give the same ranking.

Notation: `R` = goal's required signals with importance `imp(s)`, `cov(s)` = profile coverage ∈ [0,1],
`gap(s) = imp(s)·(1 − cov(s))`, `S` = signals the candidate provides.
Candidates = open opportunities (as `apply` actions) + curated growth actions.

## 1. Hard gates (excluded, reason shown in "filtered out")

| Gate | Rule |
|---|---|
| Closed | `status == closed` |
| Deadline passed | official `deadline_at < now` |
| Age | age at deadline (or now) outside `[min_age, max_age]` — only if birth date known |
| Education | profile level not in `eligibility.education_levels` |
| Country | profile country not in `eligibility.countries` |
| Cost | `cost_eur > max_cost_eur` |
| Decision | latest decision is `done`, `skipped` or `not_interested` |
| Credential value | certification whose credential tier (§6) is `Ignore` — "Nízká hodnota certifikátu pro tvůj cíl". Runs after the factors, because the tier depends on the goal. |

Unknown eligibility **passes** but lowers Probability and adds an "unverified eligibility" warning.

## 2. Factors (0–1)

| Factor | Formula | Unknown default |
|---|---|---|
| **Relevance** | `Σ_{s∈S∩R} imp(s) / Σ_{s∈S} w(s)`, `w(s)=imp(s)` if `s∈R` else 1 — how much of the item is on-goal | no signals → 0 |
| **Gap Coverage** | `Σ_{s∈S∩R} gap(s) / (sum of the 3 largest gaps)`, clamped to 1 — closing your biggest gaps scores high | no gaps → 0 |
| **CV Signal** | `(cv_signal − 1) / 4` | 0.4 |
| **Skill Gain** | mean of `1 − cov(s)` over skill-category signals in `S` | no skill signals → 0 |
| **Probability** | `certainty × clamp(0.5 + 0.5·readiness − 0.15·(difficulty − 3), 0.1, 1)`, `readiness` = mean `cov(s)` over `S`; `certainty` = 1, or 0.7 if any eligibility field is unknown | difficulty 3 |
| **Urgency** | official deadline: 1 if ≤ 7 days, linear to 0 at ≥ 90 days · expected (recurring): same curve on the next projected date × 0.5 · none: 0.2 | 0.2 |
| **Effort** *(penalty)* | `est_hours / (4 × weekly_hours_budget)`, clamped; budget defaults to 5 h/week | 0.3 |
| **Cost** *(penalty)* | 0 if free, else `cost_eur / max_cost_eur` (or `/200` without a limit), clamped | 0.2 |

Projected date for recurring items = `last_known_deadline` moved forward by whole years until it is in the future.
It is labelled "expected", never presented as an official deadline.

## 3. Priority

```
priority = Σ benefit_weight_i · factor_i  −  Σ penalty_weight_j · penalty_j
```

Weights come from the goal (template defaults below, editable per goal). Each weighted term is a
**contribution**; the API returns all of them.

| | relevance | gap_coverage | cv_signal | skill_gain | probability | urgency | effort | cost |
|---|---|---|---|---|---|---|---|---|
| AI/ML internship | 0.20 | 0.30 | 0.20 | 0.10 | 0.10 | 0.10 | 0.15 | 0.10 |
| Competition profile | 0.25 | 0.20 | 0.20 | 0.05 | 0.15 | 0.15 | 0.10 | 0.10 |

## 4. Top N and diversity

Sort by priority (ties: earlier deadline, then title). Greedy pick for Top N (default 5) with
**max 2 items of the same kind**; if that leaves the list short, it is backfilled from the
ranked list. The full ranked list is returned as well.

## 5. Explanations

Each ranked item returns:

- `factors` — all factor values, `contributions` — weighted terms,
- `reasons` — up to 3 sentences from the largest positive contributions (≥ 0.02), quoted only if
  the factor itself is high (relevance ≥ 0.3, gap ≥ 0.2, CV ≥ 0.5, skill ≥ 0.3,
  probability ≥ 0.6, urgency ≥ 0.5)
  (e.g. "Pokrývá tvoje mezery: deployment, research evidence"),
- `warnings` — e.g. unverified eligibility, deadline not published, paid.

## 6. Credential tiers (post-M1)

Implemented in `backend/app/credentials/__init__.py` (V1).

`tier_score = type_weight × issuer_reputation / 5 × goal_fit`

- Type weights: industry_certification 1.0 · skill_badge 0.6 · course_certificate 0.35 ·
  participation_badge 0.1.
- `goal_fit = (relevance + gap_coverage) / 2`, both factors from §2. A credential whose signals are
  on goal but already covered by the profile is worth half as much.
- Tiers: S ≥ 0.75, A ≥ 0.55, B ≥ 0.35, C ≥ 0.2, else Ignore. Ignore is a gate (§1).

`credential.type` and `credential.issuer_reputation` (1–5) are curated facts on certification
opportunities. Items without them get no tier. The tier is shown in the UI; it doesn't change the
priority, which already contains `cv_signal`.
