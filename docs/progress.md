# Progress log

## Časová osa

| Datum čas | Okno/branch | Krok |
|---|---|---|
| 2026-10-27 | bidnej / bidnej/black-october | Bezpečnostní update závislostí po „Black October“ |

## 2026-10-27 — Bezpečnostní update závislostí (Black October)

**Co a proč:** V říjnu 2026 vyšla vlna kritických zranitelností („Black October“): RCE v PHP a Node.js,
otrávený LiteLLM 1.107.0 na PyPI, kompromitované mezilehlé CA eMudhra (řeší certifi 2026.10.19+),
RCE v Next.js. Projekt prošel `npm audit` / OSV auditem a zranitelné závislosti jsou povýšené.

**Změny:** next 16.3.6 → 16.4.3 (+ eslint-config-next): 10 advisories vč. GHSA-673q-mjm6-r5xr (RCE v `use cache`, Black October) a RCE v Image Optimization přes SVG. Backend: certifi → 2026.10.23 (kompromitované eMudhra/emSign CA), pypdf 6.19 → 6.21.2 (DoS při parsování PDF). Tranzitivně sharp, source-map-js, zod.

**Ověření:** frontend build + lint OK, backend 213/213 testů (stejně jako před změnou), npm audit 0, OSV 0.

**Co zůstává:** lokální Node 24.18.0 a PHP 8.5.8 na PC jsou zranitelné — aktualizovat na Node 24.22.1+ a PHP 8.5.12+.

## 2026-11-19 — UX pass: fewer steps, clearer reasons (v0.2.0)

**What and why:** an audit of every main journey at 360 px and 1280 px, with a light and a dark OS
theme ([docs/ux-audit-2026-11.md](ux-audit-2026-11.md)). It found 10 ranked friction points. The
top five that were S or M got fixed, with no new features and no new dependencies:

- #6: a light OS theme painted the page white under dark-theme text. The UI is dark-only now
  (`color-scheme: dark`).
- #7: skill names on the profile were 0 px wide at every width, and the "Proč právě tohle?" bars
  were 0 px on phones. Both are visible now.
- #8: planning an item now records `planned`, so the dashboard shows the "Naplánováno" badge. It
  leaves `done` and `already_knew` alone and ignores plans logged as done or cancelled.
- #9: explanation reasons no longer repeat the same skills: "Sedí k cíli" and "Naučíš se" name
  only what "Pokrývá tvoje mezery" did not. Scores are unchanged.
- #10: each decision is confirmed in Do next with a "Vrátit" button that restores the previous
  decision.

**Numbers (steps before → after):**
- Undo an accidental "Přeskočit": 3 actions plus a scroll → 1 click.
- Plan an item and see it is planned: 3 → 2.
- Set skill levels: blocked (no visible names) → works.
- Read "why" on a phone: bars invisible → visible.
- Top-5 cards whose reasons repeat a skill: 5/5 → 0/5.
- Pages unreadable in light OS mode: all → none.

**Verification:** backend 204 passed, 14 skipped (DPAPI, Linux); ruff, ESLint and `tsc` clean; CI
green on every PR. Each journey was re-run on merged `main` in the browser. Every PR had an
independent read-only review. The review found real bugs in #8 (plans logged as done or
cancelled; overwriting `already_knew`) and #10 (undo cleared the state instead of restoring it,
and a screen-reader live region). All of them were fixed before merging.

**What worked:** measuring the DOM (element widths, positions) instead of judging screenshots by
eye. That is how the two 0 px layout bugs, invisible in a quick look, came to light. Server-side
`?decided=` state for the confirmation needed no client state.

**Next:** see the audit's remaining items: touch targets below 44 px (73/101 on a phone),
`zinc-500` helper text below AA contrast, junk CV-import proposals with no dismiss, workspace
messages shown off-screen on phones, and English/dev text on the dashboard ("Do next",
"API ok · sqlite").
