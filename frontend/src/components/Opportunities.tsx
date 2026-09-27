import Link from "next/link";

import { CandidateMeta, DeadlineQuote } from "@/components/Recommendation";
import { EmptyState } from "@/components/Section";
import { kindLabel } from "@/lib/labels";
import type { FilteredItem, RankedItem } from "@/lib/types";

type Props = {
  ranked: RankedItem[];
  filtered: FilteredItem[];
  kind: string | null;
};

export function OpportunityList({ ranked, filtered, kind }: Props) {
  const opportunities = ranked.filter((i) => i.candidate.source === "opportunity");
  const kinds = [...new Set(opportunities.map((i) => i.candidate.kind))].sort();
  const shown = kind ? opportunities.filter((i) => i.candidate.kind === kind) : opportunities;
  const excluded = filtered.filter((f) => f.candidate.source === "opportunity");

  const chip = (value: string | null, label: string) => (
    <Link
      key={value ?? "all"}
      href={value ? `/?kind=${value}` : "/"}
      scroll={false}
      className={`rounded-full border px-3 py-1 text-xs transition ${
        kind === value
          ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
          : "border-white/10 text-zinc-400 hover:text-zinc-200"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <div className="flex flex-col gap-4">
      {kinds.length > 1 && (
        <nav className="flex flex-wrap gap-2" aria-label="Filtr druhu">
          {chip(null, `Vše (${opportunities.length})`)}
          {kinds.map((k) => chip(k, kindLabel(k)))}
        </nav>
      )}
      {shown.length === 0 ? (
        <EmptyState>Žádné příležitosti — spusť načtení zdrojů.</EmptyState>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {shown.map((item) => (
            <li
              key={item.candidate.key}
              className="flex flex-col gap-2 rounded-xl border border-white/10 bg-zinc-950/40 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <a
                  href={item.candidate.url ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-zinc-100 hover:text-emerald-300 hover:underline"
                >
                  {item.candidate.title}
                </a>
                <span
                  className="shrink-0 rounded-md bg-white/5 px-2 py-0.5 text-xs tabular-nums text-zinc-300"
                  title="Skóre priority"
                >
                  {item.priority.toFixed(2)}
                </span>
              </div>
              <CandidateMeta candidate={item.candidate} tier={item.credential_tier} />
              <DeadlineQuote candidate={item.candidate} />
              {item.reasons[0] && <p className="text-sm text-zinc-300">{item.reasons[0]}</p>}
              {item.candidate.eligibility && !item.candidate.eligibility.verified && (
                <p className="text-xs text-amber-300/80">⚠ Podmínky účasti neověřené</p>
              )}
            </li>
          ))}
        </ul>
      )}
      {excluded.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-zinc-500 hover:text-zinc-300">
            Vyřazené ({excluded.length})
          </summary>
          <ul className="mt-2 space-y-1 text-zinc-400">
            {excluded.map((f) => (
              <li key={f.candidate.key}>
                {f.candidate.title} — <span className="text-zinc-500">{f.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
