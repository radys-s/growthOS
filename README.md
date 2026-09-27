# growthOS — Career Growth Engine

Personal system for growing a student's professional profile:

```
current profile → target profile → gaps → possible actions → their value → best next step
```

Competitions, olympiads, hackathons, internships, research programs, scholarships, summer schools,
certifications and strong technical projects — ranked by what actually moves *my* profile toward
*my* goal, with an explanation for every recommendation.

**Status:** V1 is built.
- **M1:** profile + goal → curated opportunities and growth actions → deterministic ranking →
  Top 5 with reasons, factor breakdown and decision buttons.
- **V1:** Devpost + Kaggle sources, an LLM deadline watcher with quote verification, and
  S/A/B/C tiers for certifications.

See [roadmap](docs/roadmap.md).

## How it works

- **Profile** (`/profile`): skills 0–4 and evidence items, both tagged with signals from
  [`backend/data/taxonomy.yaml`](backend/data/taxonomy.yaml).
- **Goal** from a template in [`backend/data/goal_templates/`](backend/data/goal_templates/):
  required signals with importance + factor weights → **gaps**.
- **Sources:**
  - Hand-curated, evidence-backed YAML in [`backend/data/curated/`](backend/data/curated/).
  - **Devpost:** open ML/AI hackathons, online or in Europe.
  - **Kaggle:** competitions; needs an API token.

  Sources refresh in the background on backend start, weekly (Mon 05:00 UTC) and via
  *Načíst zdroje*. Their state is shown in the *Zdroje* panel. Unknown deadlines stay unknown.
  Recurring events show an *expected* date, never an invented official one.
- **Deadline watcher** ([ADR 0006](docs/decisions/0006-automatic-sources-and-verified-llm-extraction.md)):
  for curated items with a `watch_url`, an LLM (OmniRoute) proposes the new deadline. Code accepts
  it only if the quote is found word for word on the page. The UI then shows the quote.
- **Certifications** get a tier (S/A/B/C) based on how much they're worth for the active goal. Tier
  Ignore is excluded.
- **Ranking** ([spec](docs/scoring.md)): hard gates → 8 factors → weighted priority → Top 5 with
  max 2 of a kind. Every number is shown under *Proč právě tohle?*.
- **Decisions:** planned / done / skipped / not interested / already knew (undo in *Rozhodnuté*).
  The header shows the weekly metric: new worthwhile items in the last 7 days.

## Docs

- [Vision](docs/vision.md) · [Architecture](docs/architecture.md) · [Data model](docs/data-model.md)
- [Scoring spec](docs/scoring.md) · [Roadmap](docs/roadmap.md) · [Decisions](docs/decisions/)
- Agent rules: [AGENTS.md](AGENTS.md)

## Run locally

Requirements: Python 3.13 + [uv](https://docs.astral.sh/uv/), Node 24, PostgreSQL 17
(or SQLite via `DATABASE_URL`).

```bash
cp .env.example backend/.env        # then fill DATABASE_URL
cd backend && uv sync && uv run python -m alembic upgrade head && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Open http://localhost:3000.

On Windows, `start.ps1` does all of it (migrations, both servers in their own windows, opens the
browser):

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

With Docker instead of native Postgres: `docker compose up -d db`.

Optional keys in `backend/.env`:
- `KAGGLE_USERNAME` / `KAGGLE_KEY` for the Kaggle source (kaggle.com → Settings → API);
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` for the deadline watcher (OmniRoute:
  `http://127.0.0.1:20128/v1`).

Without them these parts report "nenakonfigurováno" and the rest works.

## OneDrive note

The repo lives in OneDrive, which has no per-folder sync exclusion. `.venv`, `node_modules` and
`.next` are **pinned** (`attrib -U +P <dir> /S /D`) so OneDrive never turns them into cloud-only
placeholders, which would break the environments. Git is the source of truth.

Known quirk: writing `.venv/Scripts/*.exe` launchers can fail with *access denied* (sync/AV lock).
Use module form instead: `uv run python -m alembic ...`, `uv run python -m uvicorn ...`.
If `npm install` / `uv sync` hits locks, pause OneDrive syncing and retry.
