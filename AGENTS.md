# AGENTS.md — growthOS

Shared rules for every coding agent (Claude Code, Codex, …) working in this repo.
Read [docs/vision.md](docs/vision.md) and [docs/roadmap.md](docs/roadmap.md) before non-trivial work.

## What this is

Career Growth Engine: `profile → goals → gaps → best next actions → progress`.
Not a job board. Opportunity Radar is one module.

## Current focus

**Milestone 1 vertical slice** (see roadmap). Do not add Gmail, certification crawlers, project
generators or extra AI features until M1 works well. Prefer finishing the slice over broadening.

## Layout

```
backend/    FastAPI app (uv project), modules in backend/app/<module>/
frontend/   Next.js App Router + TypeScript + Tailwind
docs/       vision, architecture, data model, scoring spec, ADRs (docs/decisions/)
```

## Commands

```bash
# backend (from backend/)
uv sync
uv run uvicorn app.main:app --reload        # http://127.0.0.1:8000
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python -m alembic upgrade head   # module form: .exe launchers may be blocked (OneDrive)

# frontend (from frontend/)
npm install
npm run dev                                 # http://localhost:3000
npm run lint && npm run build
```

## Hard rules

1. **Scoring is deterministic.** LLMs extract facts / propose inputs with evidence; code computes the
   score. See [docs/scoring.md](docs/scoring.md) and ADR 0003.
2. **Never fabricate facts** about opportunities. Unknown deadline → `null` → "deadline not published".
3. **Sources** implement `SourceAdapter` in `backend/app/sources/base.py` and return
   `NormalizedOpportunity`. Adapters don't touch the DB.
4. **UTC everywhere** in storage and API; frontend localizes.
5. **Portable DB types only** (ADR 0002) — tests run on SQLite, dev on Postgres.
6. REST + Pydantic response models are the frontend/backend contract. Changing a response shape =
   update the TS types in `frontend/` in the same change.
7. Secrets only in `.env` (gitignored). Commit `.env.example` with placeholders.
8. Architecture changes → new ADR in `docs/decisions/`.

## Working with two agents

- One agent **owns** a task and implements it; the other reviews / tests independently.
- **Never edit the same files concurrently.** Split work by module or by `backend/` vs `frontend/`.
- Keep decisions and current state in `docs/` so both agents start from the same assumptions.

## Git

- Branch `main`, small logical commits, messages in Czech (imperative summary line).
- Verify author (`radys-s`), remote and branch before pushing. No force-push without asking.
