# Architecture

Modular monolith. One backend process, one frontend, one database. No microservices,
no Redis/Celery, no multi-agent architecture until a concrete need proves otherwise.

```
┌──────────────┐   REST/JSON    ┌──────────────────────────────────────────────┐
│  Next.js UI  │ ─────────────▶ │ FastAPI backend (app/)                       │
│  (frontend/) │                │                                              │
└──────────────┘                │  profile/  goals/  opportunities/            │
                                │  sources/ ──▶ adapters ──▶ NormalizedOpp.     │
                                │  ranking/  recommendations/  credentials/     │
                                │  ai/ (provider abstraction)                   │
                                │  scheduler (APScheduler, in-process)          │
                                └───────────────┬──────────────────────────────┘
                                                │ SQLAlchemy 2.0 + Alembic
                                        ┌───────▼────────┐
                                        │ PostgreSQL 17  │  (SQLite fallback)
                                        └────────────────┘
```

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind |
| Backend | Python 3.13 + FastAPI, managed with `uv` |
| DB | PostgreSQL 17 (native install); portable types so SQLite works for tests |
| ORM / migrations | SQLAlchemy 2.0 + Alembic |
| Sources | Python adapters implementing one contract |
| AI | Provider abstraction (`app/ai/provider.py`), no hardcoded model |
| Jobs | APScheduler inside the backend process |
| Deploy | Docker-ready (`docker-compose.yml`), not required for local dev |

## Backend modules (`backend/app/`)

| Module | Responsibility |
|---|---|
| `profile/` | Profile, skills, profile items (projects, competitions, achievements, certs, experience) |
| `goals/` | Goals and their required signals / factor weights |
| `opportunities/` | Stored normalized opportunities, dedup, lifecycle (open/closed/expired) |
| `sources/` | Source adapters (`base.py` contract): curated YAML, Devpost, Kaggle; runner + `source_runs`; deadline watcher (ADR 0006) |
| `taxonomy` | Controlled signal vocabulary + goal templates loaded from `backend/data/` (ADR 0005) |
| `ranking/` | Deterministic factor computation + Priority Score + explanations |
| `recommendations/` | Builds "Do next" (top N actions) from ranked opportunities + growth actions |
| `credentials/` | Credential type classification and S/A/B/C/Ignore tiering |
| `ai/` | LLM provider interface + OpenAI-compatible client (OmniRoute); extraction only, never scoring |
| `growth/` | Local import previews, confirmed outcomes, progress snapshots and weekly plans |
| `calendar/` | Dedicated Google calendar OAuth, protected tokens and three-way synchronization |
| `google/` | Shared Google OAuth (PKCE, DPAPI tokens, refresh, error mapping) for calendar and Gmail |
| `gmail/` | Read-only Gmail limited to one label; LLM extraction with deterministic quote verification (ADR 0009) |

Rules:

- Modules talk through plain functions/services, not through each other's ORM internals.
- API layer is thin; logic lives in services and is unit-testable without HTTP.
- All timestamps stored and exchanged in **UTC** (ISO 8601). Frontend localizes.
- REST is the contract between frontend and backend; response models are Pydantic.

## Data flow (V1 vertical slice)

1. A scheduler job (startup + weekly) or a manual trigger runs each enabled source adapter. Runs are
   serialized, and each writes a `source_runs` row.
2. The adapter returns `NormalizedOpportunity` items (see `app/sources/base.py`).
3. `opportunities/` upserts by `dedup_key` and keeps `fetched_at` and the evidence URL. Items
   missing from a source's snapshot are closed.
4. The deadline watcher checks each `watch_url` and stores only deadlines backed by a verbatim quote
   (ADR 0006).
5. `ranking/` builds candidates (opportunities as `apply` actions + curated growth actions),
   applies hard gates, computes factors against the goal's required signals and profile coverage.
6. `recommendations/` picks a diverse Top N with reasons/warnings → `/recommendations` endpoint.
7. The dashboard shows Do next · Opportunities · Profile gaps · Sources.

## V2 evidence and planning flow

The local import parser returns editable proposals with excerpts. Confirmed demonstrated results
become profile items with provenance, then gap coverage and the deterministic ranking update.
Completion adds a decision event and two progress snapshots. Undo appends a reversal event.
The weekly plan stores work estimates and optional UTC schedule; the UI displays Prague time.
Calendar sync uses a dedicated Google calendar and compares local and Google values against the
last acknowledged value, presenting a conflict choice when both changed. See ADRs 0007 and 0008.

## V3 Gmail flow

After the source adapters and the deadline watcher, the runner's Gmail step lists messages with
the user's label, skips ids already processed, and sends each new body to the LLM with a
structured schema. Code keeps only claims whose quote is verbatim in the message; dates, URLs,
organizers and results must appear there too. Opportunities are inserted (or fill a missing
deadline of a known opportunity with the same URL); achievements become import proposals for the
user to confirm. See ADR 0009.
