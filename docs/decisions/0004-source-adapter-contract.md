# 0004 — Source adapter contract

- Status: accepted (2026-09-27)

## Context
Plan: 5–10 high-quality sources rather than 100 fragile scrapers. They must be swappable and testable.

## Decision
Every source implements `SourceAdapter` (`backend/app/sources/base.py`): an `id`, a `name`, and
`fetch() -> list[NormalizedOpportunity]`. Adapters never write to the DB; the `opportunities`
module upserts by `dedup_key`. Prefer official APIs / structured feeds; a curated YAML source is a
first-class adapter. Each item carries `evidence_url` and `fetched_at`.

## Consequences
+ Adapters are pure and unit-testable with recorded fixtures.
− Normalization rules must be kept consistent across adapters (shared helpers in `sources/`).
