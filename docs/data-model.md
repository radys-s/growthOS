# Data model (draft for V1)

Draft — to be confirmed before the first migration with real tables.
All `*_at` columns are UTC. IDs are UUIDs. Enums stored as strings (portable across Postgres/SQLite).

## Profile

Single user in V1, but keep `profile_id` foreign keys so multi-profile is not a rewrite.

| Field | Type | Notes |
|---|---|---|
| id | uuid | |
| name | str | |
| birth_date | date? | needed for age-based eligibility |
| country | str | ISO 3166-1 alpha-2, e.g. `CZ` |
| education_level | enum | `high_school`, `bachelor`, `master`, … |
| graduation_year | int? | |
| max_cost_eur | int? | hard gate for paid opportunities |
| weekly_hours_budget | int? | used by Effort penalty |

## Skill

| Field | Type | Notes |
|---|---|---|
| profile_id | fk | |
| name | str | normalized (e.g. `pytorch`, `fastapi`) |
| level | int 0–4 | none / basic / working / strong / expert |
| evidence_item_id | fk? | ProfileItem proving it |

## ProfileItem

Everything that is *evidence* on a CV.

| Field | Type | Notes |
|---|---|---|
| kind | enum | `project`, `competition`, `achievement`, `certification`, `experience`, `publication` |
| title, description | str | |
| result | str? | e.g. "81st / 5000", "Gold" |
| skills | list[str] | |
| url | str? | GitHub, certificate, leaderboard |
| started_at, finished_at | date? | |
| signal_strength | int 0–4 | how strong it looks externally (manual in V1) |

## Goal

| Field | Type | Notes |
|---|---|---|
| title | str | e.g. "AI/ML internship summer 2027" |
| kind | enum | `internship`, `university_abroad`, `competition_profile`, `research`, `custom` |
| target_date | date? | |
| required_signals | list[RequiredSignal] | what a strong profile for this goal contains |
| weights | dict | per-factor weights, see [scoring.md](scoring.md) |
| active | bool | |

`RequiredSignal` = `{ name, category, importance 1–3 }`, e.g. `{ "deployment", "skill", 2 }`,
`{ "research evidence", "publication", 3 }`. **Gaps** = required signals not covered by profile items/skills.

## Opportunity

| Field | Type | Notes |
|---|---|---|
| kind | enum | `competition`, `olympiad`, `hackathon`, `internship`, `scholarship`, `program`, `summer_school`, `certification` |
| title, organizer, description | str | |
| url | str | canonical page |
| deadline_at | datetime? | `null` = not published (never guessed) |
| starts_at, ends_at | datetime? | |
| eligibility | Eligibility | structured, see below |
| cost_eur | int? | 0 = free, `null` = unknown |
| location | str | `online` or city/country |
| difficulty | int 1–5? | |
| est_hours | int? | |
| skills_taught | list[str] | |
| source | str | adapter id |
| source_ref | str | id in the source |
| evidence_url | str | where the facts come from |
| fetched_at | datetime | |
| dedup_key | str | normalized title + organizer + deadline date |
| status | enum | `open`, `closed`, `expired`, `unknown` |

`Eligibility` = `{ min_age?, max_age?, education_levels?: [...], countries?: [...], team_size?: [min,max], notes? }`.
Unknown fields stay `null` and are shown as "unknown", never assumed to pass or fail.

## GrowthAction

An action the user can take; may or may not be backed by an Opportunity.

| Field | Type | Notes |
|---|---|---|
| kind | enum | `apply`, `build`, `learn`, `certify`, `publish`, `obtain_credential` |
| title | str | |
| opportunity_id | fk? | for `apply` / `certify` |
| covers_signals | list[str] | which RequiredSignals it addresses |
| est_hours | int? | |
| origin | enum | `source`, `manual`, `suggested` |

## Credential

Classification layer for certifications/badges.

| Field | Type | Notes |
|---|---|---|
| name, issuer | str | |
| type | enum | `industry_certification`, `skill_badge`, `course_certificate`, `participation_badge` |
| issuer_reputation | int 1–5 | curated |
| proctored | bool? | |
| cost_eur, est_hours | int? | |

Tier (S/A/B/C/Ignore) is computed per profile+goal, not stored as a fixed attribute.

## ActionDecision

History of what the user did with a recommendation — feeds the success metric.

| Field | Type | Notes |
|---|---|---|
| action_id / opportunity_id | fk | |
| decision | enum | `done`, `planned`, `skipped`, `not_interested`, `already_knew` |
| note | str? | |
| decided_at | datetime | |

Weekly success metric = count of recommendations shown that were **not** `already_knew`
and ended as `planned` or `done`.
