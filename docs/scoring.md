# Scoring & ranking spec

Scoring is **deterministic and explainable**. The LLM may extract facts and propose factor
*inputs* (with evidence), but the final number is always computed by code from stored inputs.
A score of "92 %" with no traceable reason is a bug.

## 1. Hard gates (before any scoring)

An opportunity/action is **excluded** — and shown in a "filtered out" list with the reason — when:

| Gate | Rule |
|---|---|
| Deadline | `deadline_at < now` |
| Age | profile age at deadline outside `[min_age, max_age]` |
| Education | profile `education_level` not in `eligibility.education_levels` |
| Country | profile `country` not in `eligibility.countries` |
| Cost | `cost_eur > profile.max_cost_eur` |

Unknown eligibility fields **pass** the gate but lower `Probability` and get an "unverified" badge.

## 2. Factors (each 0–1, each with a one-line explanation)

| Factor | Meaning | V1 input |
|---|---|---|
| Relevance | fits the goal? | overlap of opportunity kind/skills with goal required signals |
| CV Signal | how strong the result looks externally | curated per source/organizer + kind (olympiad > participation badge) |
| Skill Gain | what I actually learn | `skills_taught` not yet at level ≥ 3 in profile |
| Gap Coverage | fixes one of my weaknesses? | weighted share of uncovered required signals it covers |
| Probability | I'm eligible and have a chance | eligibility certainty × difficulty vs. relevant skill levels |
| Urgency | deadline pressure | 1 when ≤ 7 days, decays to 0 at ≥ 90 days; `null` deadline → 0.3 |
| Effort *(penalty)* | time cost | `est_hours / weekly_hours_budget`, clamped |
| Cost *(penalty)* | money | 0 free, scaled by `cost_eur / max_cost_eur` |

## 3. Priority score

```
priority = Σ w_i · f_i  −  Σ p_j · c_j        (f = benefits, c = penalties)
```

- Weights live on the **Goal** (`goal.weights`), so a research goal can favour Gap Coverage and
  CV Signal while a competition-profile goal favours Probability and Urgency.
- Default weights (starting point, to be tuned against real usage):

| relevance | cv_signal | skill_gain | gap_coverage | probability | urgency | effort | cost |
|---|---|---|---|---|---|---|---|
| 0.25 | 0.20 | 0.10 | 0.25 | 0.10 | 0.10 | 0.15 | 0.10 |

- Output per item: `priority`, all factor values, and the 2–3 factors that contributed most,
  rendered as human sentences ("Covers your *deployment* gap", "Deadline in 5 days").

## 4. Credential tiers

```
tier_score = type_weight × issuer_reputation_norm × goal_fit
```

| type | type_weight |
|---|---|
| industry_certification | 1.0 |
| skill_badge | 0.6 |
| course_certificate | 0.35 |
| participation_badge | 0.1 |

Thresholds → S ≥ 0.75, A ≥ 0.55, B ≥ 0.35, C ≥ 0.2, else **Ignore** (explicitly recommended to skip,
with "low incremental CV value" explanation).

## 5. Unknowns

- Missing input → factor uses a documented neutral default and the explanation says "unknown".
- Never fabricate deadlines, eligibility or costs. `null` deadline is displayed as "deadline not published".
