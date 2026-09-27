# 0002 — PostgreSQL 17 native, SQLite as fallback

- Status: accepted (2026-09-27)

## Context
No Docker on the dev laptop (16 GB RAM, no dGPU); Docker Desktop is heavy there.

## Decision
Native PostgreSQL 17 (winget) for development. Keep `docker-compose.yml` so the project stays
Docker-ready. Models use only portable SQLAlchemy types (`Uuid`, `JSON`, `String` enums, timezone-aware
`DateTime`), so `DATABASE_URL=sqlite:///...` works for unit tests and as an emergency fallback.

## Consequences
+ Real Postgres behaviour from day one, no container overhead.
− No Postgres-only features (JSONB operators, arrays) unless this ADR is revisited.
