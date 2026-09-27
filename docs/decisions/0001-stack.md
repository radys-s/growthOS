# 0001 — Stack: Next.js + FastAPI modular monolith

- Status: accepted (2026-09-27)

## Context
Single-user personal system, one developer + AI agents (Claude Code, Codex). Scraping/extraction
and ML-adjacent logic is most natural in Python; UI benefits from the React ecosystem.

## Decision
Next.js + TypeScript frontend, Python 3.13 + FastAPI backend, SQLAlchemy 2.0 + Alembic,
`uv` for Python deps, APScheduler in-process for jobs. One deployable backend, no microservices,
no Redis/Celery, no agent framework.

## Consequences
+ Simple to run locally, simple to reason about, easy for agents to navigate.
− Two languages/toolchains. Background jobs die with the process (acceptable for weekly runs).
