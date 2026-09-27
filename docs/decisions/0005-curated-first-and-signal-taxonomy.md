# 0005 — Curated-first sources and a controlled signal taxonomy

- Status: accepted (2026-09-27)

## Context
The most valuable opportunities for a Czech high-school student interested in AI (IOAI, SOČ,
national olympiads, CERN Beamline for Schools, research programs) are few, recurring and poorly
structured on the web — scrapers would be fragile and noisy. Ranking also needs to compare goals,
profile and opportunities without an LLM (M1 has none, ADR 0003).

## Decision
1. M1 has exactly one source: a **curated YAML adapter** (`backend/data/curated/`), each item with an
   official evidence URL. Automatic adapters (Kaggle, Devpost) come after M1 works.
2. A **controlled signal taxonomy** (`backend/data/taxonomy.yaml`) is the shared vocabulary for goal
   requirements, profile evidence and what opportunities/actions provide. Unknown signal ids are a
   validation error.
3. **Goal templates** define required signals + weights; goals are instantiated from them.
4. Recurring events without a published deadline keep `deadline_at = null` and carry
   `recurrence` + `last_known_deadline`; the UI says "expected", never presents it as official.

## Consequences
+ Deterministic gap analysis and relevance; high-quality data from day one.
+ Adding a signal is a one-line YAML change.
− Curated data needs a weekly human review; taxonomy must stay small (≈ 25 signals).
