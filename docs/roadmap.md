# Roadmap

## Milestone 0 — Bootstrap ✅

- [x] Repo, docs, conventions (`AGENTS.md`)
- [x] Backend skeleton (FastAPI, SQLAlchemy, Alembic, `/health`, source adapter contract)
- [x] Frontend skeleton (dashboard with three empty sections)

## Milestone 1 — Vertical slice (next)

> Profile + goal → real opportunities from 2–3 sources → normalize → rank → Top 5 with explanation.

- [ ] Confirm data model ([data-model.md](data-model.md)) → first real migration
- [ ] Profile + Goal CRUD API (manual input) + simple forms in UI
- [ ] Source: **curated YAML** (`backend/data/curated/*.yaml`) — olympiads, IOAI, SOČ, summer schools, programs
- [ ] Source: **Kaggle competitions** (official API)
- [ ] Source: **Devpost hackathons** (public listing JSON)
- [ ] Upsert + dedup by `dedup_key`
- [ ] Ranking: hard gates + factors + priority per [scoring.md](scoring.md), unit-tested
- [ ] `/recommendations?goal_id=…` → Top 5 with explanation lines
- [ ] Dashboard: Do next · Opportunities · Profile gaps filled from API
- [ ] Decision buttons: done / planned / skip / not interested / **already knew**
- [ ] Weekly run via APScheduler

**Exit criterion:** for one real goal, Top 5 is something I'd actually act on, and at least one item
is new to me.

## Later (only after M1 works well)

- V1 polish: 5–10 quality adapters total, credential tiering in UI
- V2: automatic gap analysis, CV import, GitHub analysis, calendar/deadlines, decision history, learning recs
- V3: Gmail source adapter (extraction → opportunity / deadline / achievement)
- V4: Career Strategist — long-horizon roadmap that re-plans

## Open questions

1. Which 2–3 goals to model first? (proposal: AI/ML internship 2027, stronger competition profile)
2. Curated source ownership: who adds entries and how often (proposal: YAML in repo, reviewed weekly)?
3. Kaggle API needs a Kaggle token — OK to use Tomáš's own account token locally (`.env`)?
4. LLM provider for extraction in M1 — needed at all, or rule-based extraction first? (proposal: none in M1)
