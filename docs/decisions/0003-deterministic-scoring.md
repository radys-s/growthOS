# 0003 — Deterministic, explainable scoring; LLM only for extraction

- Status: accepted (2026-09-27)

## Context
The value of the product is trust in "what should I do next". An opaque LLM score ("92 %") can't
be debugged, tuned or trusted.

## Decision
Priority is a weighted sum of separately stored factors (see `docs/scoring.md`), computed in code.
LLMs may extract structured fields and propose factor inputs **with evidence**; they never output
the final score. Unknowns are explicit, never guessed.

## Consequences
+ Every ranking is reproducible and explainable; weights are tunable per goal.
− Factor inputs need curation (CV Signal, issuer reputation) — acceptable at V1 scale.
