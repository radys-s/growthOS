# Roadmap

## Milestone 0 — Bootstrap ✅

- [x] Repo, docs, conventions (`AGENTS.md`)
- [x] Backend skeleton (FastAPI, SQLAlchemy, Alembic, `/health`, source adapter contract)
- [x] Frontend skeleton (dashboard with three empty sections)

## Milestone 1 — Vertical slice ✅ (built 2026-09-27, exit criterion awaiting Tomáš's review)

> Profile + goal → curated opportunities → rank → Top 5 with explanation → decide.

Decisions (2026-09-27): goals **AI/ML internship 2027** + **stronger competition profile**;
source = **curated YAML only**; **no LLM** in M1 (ADR 0005).

- [x] Design upgrade: signal taxonomy, goal templates, action-centric ranking, deadline honesty (ADR 0005)
- [x] Persistence: models + migration, Profile/Goal API, seed (taxonomy, templates, example profile)
- [x] Curated source adapter + ingestion (upsert by `dedup_key`) + weekly scheduler job
- [x] Curated data: real, evidence-backed opportunities + generic growth actions
- [x] Ranking engine per [scoring.md](scoring.md) with unit tests
- [x] API: recommendations, gaps, opportunities, decisions
- [x] Dashboard: Do next (reasons, factors) · Profile gaps · Opportunities · decision buttons
- [x] Profile page: skills, items, goal selection
- [x] E2E verification in browser

**Exit criterion:** for one real goal, Top 5 is something I'd actually act on, and at least one item
is new to me. → Tomáš checks this on the real profile; tune weights/curated data if not.

Known M1 limits: single user, no auth (local only); curated data needs manual weekly review;
all curated eligibility is unverified; decisions can be undone but have no history view.

## V1 — More sources + credential tiering ✅ (built 2026-09-27)

Decisions (2026-09-27): sources Kaggle API, Devpost, Czech competitions via the deadline watcher,
and more curated data. The LLM is a free model via OmniRoute and only extracts facts (ADR 0006).

- [x] Source infrastructure: shared HTTP client, `source_runs`, `GET /sources`, `SOURCES_ENABLED`
- [x] Devpost adapter: open ML/AI hackathons, online or in Europe
- [x] Kaggle adapter: official API with basic auth; without a token it reports "not configured"
- [x] OmniRoute provider + deadline watcher: verbatim quote, date in the quote, future date (ADR 0006)
- [x] Credential tiering S/A/B/C/Ignore ([scoring.md §6](scoring.md))
- [x] Curated data: Otevřená věda, Nachytej AI, 4 certifications with type and reputation, `watch_url`
- [x] Frontend: sources panel, Devpost/Kaggle badge, tier badge, deadline quote
- [x] E2E in the browser (Devpost live, sources panel, badges)

**Needs Tomáš:**
- put `KAGGLE_USERNAME`/`KAGGLE_KEY` and `LLM_BASE_URL`/`LLM_API_KEY` in `backend/.env`;
- have OmniRoute running.

Until then Kaggle and the deadline watcher show "nenakonfigurováno" and are verified only on
fixtures.

To tune after review:
- course certificates (NVIDIA DLI, Kaggle Learn) fall into Ignore under the spec formula;
- hackathons dominate the full ranking; Top 5 is held by diversity.

## V2 — Evidence, imports, planning and progress

Implementation completed 2026-09-28. Functional verification and live Google authorization are
tracked separately.

- [x] Local PDF/DOCX/text CV proposals and public GitHub metadata/README/manifests; explicit
  review and confirmation, provenance and duplicate protection (ADR 0007)
- [x] Completion results and confirmed evidence change gaps and recommendations; append-only
  decision history and progress snapshots
- [x] Weak credential value no longer excludes learning; discovered and explicitly useful counts
  are separate
- [x] Weekly work plans with capacity warning and optional Prague time
- [x] Dedicated Google calendar OAuth, locally protected tokens, two-way sync, conflict choice,
  retry and recovery handling (ADR 0008)
- [x] API/TypeScript contracts and Czech UI
- [x] Startup checks migrations and both services before opening the dashboard
- [ ] Live Google synchronization after OAuth client setup and account authorization
- [ ] Tomáš's qualitative assessment of recommendation quality with his real profile

## Later

- V3: Gmail source adapter (extraction → opportunity / deadline / achievement)
- V4: Career Strategist — long-horizon roadmap that re-plans

## Open questions

1. ~~Kaggle token + Devpost adapter~~ — done in V1.
2. ~~LLM provider for extraction~~ — OmniRoute free model, any OpenAI-compatible endpoint (ADR 0006).
3. Curated data review cadence — proposal: weekly, together with the dashboard check.
