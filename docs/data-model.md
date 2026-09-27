# Data model (Milestone 1)

All `*_at` columns are UTC (timezone-aware on read, also on SQLite). IDs are UUIDs.
Enums are stored as strings; lists/dicts as `JSON` (portable across Postgres/SQLite, ADR 0002).

## Core idea: signals

Everything is matched through a **controlled signal taxonomy** (`backend/data/taxonomy.yaml`, ADR 0005).
A *signal* is something a strong profile can show: a skill (`deployment`, `deep_learning`),
evidence (`ml_competition_result`, `research_evidence`) or a credential (`recognized_credential`).

- Goals **require** signals (with importance 1–3).
- The profile **has** signals (skills with level, items with strength).
- Opportunities and growth actions **provide** signals.

Gap analysis and relevance are then plain set arithmetic — deterministic, explainable, no fuzzy text matching.

## Profile (single user in M1)

| Field | Type | Notes |
|---|---|---|
| id | uuid | |
| name | str | |
| birth_date | date? | age gates; unknown → gate passes as "unverified" |
| country | str | ISO 3166-1 alpha-2 (`CZ`) |
| education_level | enum | `high_school`, `bachelor`, `master`, `phd` |
| graduation_year | int? | |
| max_cost_eur | int? | hard gate for paid items |
| weekly_hours_budget | int? | Effort penalty (default 10 h) |

### ProfileSkill

`{ signal, level 0–4 }` — none / basic / working / strong / expert. Unique per (profile, signal).

### ProfileItem — evidence on the CV

| Field | Type | Notes |
|---|---|---|
| kind | enum | `project`, `competition`, `achievement`, `certification`, `experience`, `publication` |
| title, description, result, url | str | result e.g. "81st / 5000" |
| signals | list[signal] | what the item proves |
| strength | int 0–4 | how strong it looks externally |
| achieved_on | date? | |

**Coverage** of signal `s` = `max(skill_level(s), max strength of items proving s) / 4` ∈ [0, 1].

## Goal

Instantiated from a **goal template** (`backend/data/goal_templates/*.yaml`), then editable.

| Field | Type | Notes |
|---|---|---|
| template_id | str | e.g. `ai_ml_internship` |
| title | str | |
| target_date | date? | |
| required_signals | list[{signal, importance 1–3}] | |
| weights | dict[factor → float] | see [scoring.md](scoring.md) |
| active | bool | |

**Gap** of required signal `s` = `importance(s) × (1 − coverage(s))`.

## Opportunity (from sources)

| Field | Type | Notes |
|---|---|---|
| kind | enum | `competition`, `olympiad`, `hackathon`, `internship`, `scholarship`, `program`, `summer_school`, `certification` |
| title, organizer, description, url | str | |
| deadline_at | datetime? | **only when officially published** |
| recurrence | enum? | `yearly`, `rolling` — for events that repeat |
| last_known_deadline | datetime? | previous edition's deadline (evidence-backed) |
| starts_at, ends_at | datetime? | |
| eligibility | JSON | `{min_age, max_age, education_levels, countries, team_size_min/max, notes}`, `null` = unknown |
| cost_eur | int? | 0 free, `null` unknown |
| location | str | `online` or place |
| difficulty | int 1–5? | |
| est_hours | int? | |
| signals | list[signal] | what doing it provides |
| cv_signal | int 1–5? | curated external prestige |
| cv_signal_reason | str? | one-line rationale |
| source, source_ref | str | adapter id + id in source |
| evidence_url | str | where the facts come from |
| fetched_at | datetime | |
| dedup_key | str (unique) | normalized title + organizer + deadline date |
| status | enum | `open`, `closed` |

Deadline display: `deadline_at` → exact date · else `recurrence + last_known_deadline` → "expected ~<month>, not yet published" · else "deadline not published".

## GrowthAction (non-opportunity actions)

Curated generic actions that close gaps no external opportunity covers (e.g. "Deploy a model as a public API").
Loaded from `backend/data/curated/actions.yaml`.

| Field | Type | Notes |
|---|---|---|
| kind | enum | `build`, `learn`, `certify`, `publish`, `apply` |
| title, description | str | |
| signals | list[signal] | |
| est_hours | int? | |
| difficulty | int 1–5? | |
| cv_signal, cv_signal_reason | | as above |
| source_ref | str (unique) | |

Every open Opportunity is ranked as an implicit `apply` action, so both types share one ranking.

## Decision

| Field | Type | Notes |
|---|---|---|
| profile_id | uuid | |
| target_type | enum | `opportunity`, `action` |
| target_id | uuid | |
| status | enum | `planned`, `done`, `skipped`, `not_interested`, `already_knew` |
| note | str? | |
| created_at | datetime | append-only log; latest per target wins (strictly increasing) |

Effect on ranking: `done`, `skipped`, `not_interested` → hidden; `planned` → shown with badge;
`already_knew` → shown, excluded from the novelty metric.

**Novelty (weekly success metric):** items first seen in the last 7 days; `new_worthwhile` = those
that pass the gates and are not marked `already_knew`. Returned with `/recommendations`.

## API (M1)

`GET /taxonomy` · `GET/PUT /profile` · `PUT /profile/skills` · `POST/DELETE /profile/items` ·
`GET /goal-templates` · `GET/POST /goals` · `PATCH/DELETE /goals/{id}` · `GET /goals/{id}/gaps` ·
`GET /opportunities` · `POST /sources/run` · `GET /recommendations?goal_id=&top_n=` ·
`GET/POST /decisions` · `GET /health`

**Weekly novelty metric** = items decided `planned`/`done` in the last 7 days that were *not* marked `already_knew`.
