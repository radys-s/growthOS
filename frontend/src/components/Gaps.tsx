import { EmptyState } from "@/components/Section";
import type { GapItem } from "@/lib/types";

export function GapList({ gaps }: { gaps: GapItem[] }) {
  if (gaps.length === 0) return <EmptyState>Cíl nemá žádné požadované signály.</EmptyState>;
  return (
    <ul className="flex flex-col gap-3">
      {gaps.map((gap) => {
        const pct = Math.round(gap.coverage * 100);
        return (
          <li key={gap.signal}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className={gap.gap > 0 ? "text-zinc-100" : "text-zinc-500"}>{gap.label}</span>
              <span
                className="shrink-0 text-xs tracking-widest text-amber-300"
                title={`Důležitost ${gap.importance}/3`}
              >
                {"●".repeat(gap.importance)}
                <span className="text-zinc-700">{"●".repeat(3 - gap.importance)}</span>
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
                <div
                  className={`h-full rounded-full ${pct >= 75 ? "bg-emerald-400/70" : pct >= 25 ? "bg-amber-400/70" : "bg-rose-400/70"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="w-9 text-right text-xs tabular-nums text-zinc-400">{pct} %</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
