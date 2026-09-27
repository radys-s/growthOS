# Roadmap

## Milestone 0 — Bootstrap ✅

- [x] Repo, docs, conventions (`AGENTS.md`)
- [x] Backend skeleton (FastAPI, SQLAlchemy, Alembic, `/health`, source adapter contract)
- [x] Frontend skeleton (dashboard with three empty sections)

## Milestone 1 — Vertical slice (in progress)

> Profile + goal → curated opportunities → rank → Top 5 with explanation → decide.

Decisions (2026-09-27): goals **AI/ML internship 2027** + **stronger competition profile**;
source = **curated YAML only**; **no LLM** in M1 (ADR 0005).

- [x] Design upgrade: signal taxonomy, goal templates, action-centric ranking, deadline honesty (ADR 0005)
- [x] Persistence: models + migration, Profile/Goal API, seed (taxonomy, templates, example profile)
- [x] Curated source adapter + ingestion (upsert by `dedup_key`) + weekly scheduler job
- [x] Curated data: real, evidence-backed opportunities + generic growth actions
- [x] Ranking engine per [scoring.md](scoring.md) with unit tests
- [ ] API: recommendations, gaps, opportunities, decisions
- [ ] Dashboard: Do next (reasons, factors) · Profile gaps · Opportunities · decision buttons
- [ ] Profile page: skills, items, goal selection
- [ ] E2E verification in browser

**Exit criterion:** for one real goal, Top 5 is something I'd actually act on, and at least one item
is new to me.

## Later (only after M1 works well)

- V1 polish: 5–10 quality adapters total, credential tiering in UI
- V2: automatic gap analysis, CV import, GitHub analysis, calendar/deadlines, decision history, learning recs
- V3: Gmail source adapter (extraction → opportunity / deadline / achievement)
- V4: Career Strategist — long-horizon roadmap that re-plans

## Open questions

1. Kaggle token + Devpost adapter — after M1 (decided 2026-09-27).
2. Which LLM provider for extraction once rules stop being enough (OmniRoute free model vs Claude API)?
3. Curated data review cadence — proposal: weekly, together with the dashboard check.
