import { formatPrague, SOURCE_SETUP_HINT } from "@/lib/labels";
import type { SourceStatus } from "@/lib/types";

function state(source: SourceStatus): { dot: string; text: string } {
  if (!source.enabled) return { dot: "bg-zinc-600", text: "vypnuto (SOURCES_ENABLED)" };
  if (!source.configured) return { dot: "bg-amber-400", text: "nenakonfigurováno" };
  if (!source.last_run) return { dot: "bg-zinc-500", text: "zatím neběželo" };
  const when = formatPrague(source.last_run);
  if (source.last_status === "error") return { dot: "bg-rose-400", text: `chyba · ${when}` };
  if (source.last_status === "not_configured")
    return { dot: "bg-amber-400", text: `nenakonfigurováno · ${when}` };
  return {
    dot: "bg-emerald-400",
    text: `${source.last_fetched ?? 0} položek · ${when}`,
  };
}

export function SourceList({ sources }: { sources: SourceStatus[] }) {
  return (
    <ul className="flex flex-col gap-2.5 text-sm">
      {sources.map((source) => {
        const { dot, text } = state(source);
        const hint = source.enabled && !source.configured ? SOURCE_SETUP_HINT[source.id] : null;
        return (
          <li key={source.id} className="flex flex-col gap-0.5">
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-zinc-200">
                <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} aria-hidden />
                {source.name}
              </span>
              <span className="text-right text-xs text-zinc-400">{text}</span>
            </div>
            {hint && <p className="pl-4 text-xs text-amber-300/80">{hint}</p>}
            {source.last_status === "error" && source.last_error && (
              <p className="line-clamp-2 pl-4 text-xs text-rose-300/80" title={source.last_error}>
                {source.last_error}
              </p>
            )}
            {source.last_status === "ok" && source.last_error && (
              <p className="line-clamp-2 pl-4 text-xs text-zinc-500" title={source.last_error}>
                Upozornění: {source.last_error}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
