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
