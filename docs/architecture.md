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
| `sources/` | Source adapters (`base.py` contract), fetching, normalization |
| `ranking/` | Deterministic factor computation + Priority Score + explanations |
| `recommendations/` | Builds "Do next" (top N actions) from ranked opportunities + growth actions |
| `credentials/` | Credential type classification and S/A/B/C/Ignore tiering |
| `ai/` | LLM provider interface; used for extraction and reasoning, never final scoring |

Rules:

- Modules talk through plain functions/services, not through each other's ORM internals.
- API layer is thin; logic lives in services and is unit-testable without HTTP.
- All timestamps stored and exchanged in **UTC** (ISO 8601). Frontend localizes.
- REST is the contract between frontend and backend; response models are Pydantic.

## Data flow (V1 vertical slice)

1. Scheduler (or manual trigger) runs each enabled source adapter.
2. Adapter returns `NormalizedOpportunity` items (see `app/sources/base.py`).
3. `opportunities/` upserts by `dedup_key`, keeps `fetched_at` and evidence URL.
4. `ranking/` applies hard gates, then computes factors per (opportunity, goal).
5. `recommendations/` picks Top N with explanation lines → `/recommendations` endpoint.
6. Dashboard shows Do next · Opportunities · Profile gaps.
