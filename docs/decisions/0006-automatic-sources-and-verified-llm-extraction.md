# 0006 — Automatic sources and LLM deadline extraction with quote verification

- Status: accepted (2026-09-27)

## Context
V1 adds automatic sources (Devpost, Kaggle) next to the curated YAML. The most valuable Czech items
(olympiads, SOČ, Česká AI olympiáda, …) have no API. Their next deadline appears as free text on an
official page, often weeks after we add the item. Guessing it would break the "never fabricate
facts" rule, and a human cannot check every page weekly.

## Decision
1. **Automatic adapters** (`sources/devpost.py`, `sources/kaggle.py`) follow ADR 0004. They get a
   shared httpx client injected, never touch the DB, and fail soft. The runner writes one
   `source_runs` row per source and run: `ok`, `error` or `not_configured` (missing credentials).
   `GET /sources` exposes the latest row. `SOURCES_ENABLED` switches sources on or off.
2. The **deadline watcher** (`sources/deadline_watch.py`) is an enrichment step after the adapters,
   not an adapter, because it updates existing rows. It runs for open items with a `watch_url` that
   don't already have a future deadline from their source.
3. An **LLM** proposes `{deadline_date, quote}` from the page text. It uses any OpenAI-compatible
   endpoint; the default is local OmniRoute (`LLM_BASE_URL`, `LLM_MODEL`). **Code accepts the
   proposal only if all of these hold**:
   - the quote appears verbatim in the page, ignoring whitespace and case;
   - the date is written in the quote, with a matching year if the quote has one;
   - the date is in the future and at most ~18 months ahead.

   Otherwise the deadline stays unknown. A stored deadline carries
   `deadline_source="extracted"`, the quote and `deadline_checked_at`. The API returns it as an
   official deadline with `quote` and `quote_url`, so the UI shows its evidence.
4. **No wasted LLM calls:** the page text is hashed together with the prompt version. An unchanged
   page is not sent again. On a network or LLM failure the hash is left alone, so the page is
   retried on the next run.
5. **Precedence:** a deadline published by the source (e.g. `deadline_at` in curated YAML) always
   wins. A snapshot without a deadline does not erase an extracted one. An extracted deadline is
   withdrawn once its quote disappears from the page.
6. **Scoring is unchanged** (ADR 0003). An extracted deadline is an input like any other and only
   exists after the verification above.

## Consequences
- Czech deadlines appear automatically, and every one of them is backed by a sentence from an
  official page.
- The LLM can still choose the wrong real sentence from the page, such as an event day instead of
  the registration deadline. The quote shown in the UI makes such mistakes visible to the user. The
  prompt asks for registration and submission deadlines only.
- Without `LLM_BASE_URL` the watcher reports `not_configured` and everything else works.
- Devpost's JSON list is undocumented and may change; its failure shows up in the sources panel.
