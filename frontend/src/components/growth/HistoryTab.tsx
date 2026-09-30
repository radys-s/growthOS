"use client";

import { useEffect, useState } from "react";
import { growthApi } from "@/lib/growth-api";
import { DECISION_LABELS } from "@/lib/labels";
import type { DecisionEvent, DecisionStatus, ProgressSnapshot } from "@/lib/types";
import { button, dateLabel, Panel, type Workspace } from "./ui";

export default function HistoryTab({ ws }: { ws: Workspace }) {
  const { fail } = ws;
  const [events, setEvents] = useState<DecisionEvent[]>([]);
  const [progress, setProgress] = useState<ProgressSnapshot[]>([]);

  useEffect(() => {
    Promise.all([
      growthApi<DecisionEvent[]>("/history").then(setEvents),
      growthApi<ProgressSnapshot[]>("/progress").then(setProgress),
    ]).catch(() => fail("Backend neodpovídá. Spusť growthOS a obnov stránku."));
  }, [fail]);

  return (
    <>
      <Panel title="Změny pokrytí cílů">
        <p className="text-sm text-zinc-400">
          Záznam před a po potvrzení. Vyšší pokrytí samo o sobě nedokazuje lepší kvalitu doporučení.
        </p>
        {!progress.length && <p>Zatím nejsou potvrzené nové výsledky.</p>}
        <ol className="space-y-4">
          {progress.map((p) => (
            <li key={p.id} className="border-l-2 border-emerald-400/30 pl-4">
              <p>{p.reason}</p>
              <p className="text-xs text-zinc-500">
                {dateLabel(p.created_at)} · cíl {p.goal_id.slice(0, 8)}
              </p>
              <p className="mt-1 text-sm text-zinc-300">
                {Object.entries(p.coverage)
                  .map(([key, value]) => `${key}: ${Math.round(value * 100)} %`)
                  .join(" · ")}
              </p>
            </li>
          ))}
        </ol>
      </Panel>
      <Panel title="Historie rozhodnutí">
        <p className="text-sm text-zinc-400">
          Vrácení rozhodnutí přidá nový záznam. Dřívější výsledky ani důkazy nemaže.
        </p>
        {!events.length && <p>Zatím žádná rozhodnutí.</p>}
        <ol className="space-y-3">
          {events.map((event) => (
            <li
              key={event.id}
              className="flex flex-wrap justify-between gap-2 border-b border-white/10 pb-3"
            >
              <div>
                <p>
                  {DECISION_LABELS[event.status as DecisionStatus] ?? event.status} ·{" "}
                  {event.note ?? event.target_id.slice(0, 8)}
                </p>
                <p className="text-xs text-zinc-500">{dateLabel(event.created_at)}</p>
              </div>
              {event.status !== "reversed" && (
                <button
                  className={button}
                  disabled={ws.busy}
                  onClick={() =>
                    ws.run(async () => {
                      await growthApi(
                        `/decisions/${event.target_type}/${event.target_id}`,
                        "DELETE",
                      );
                      setEvents(await growthApi<DecisionEvent[]>("/history"));
                      ws.notify("Rozhodnutí vráceno; historie a důkazy zůstaly zachovány.");
                    })
                  }
                >
                  Vrátit rozhodnutí
                </button>
              )}
            </li>
          ))}
        </ol>
      </Panel>
    </>
  );
}
