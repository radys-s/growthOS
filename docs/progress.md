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
