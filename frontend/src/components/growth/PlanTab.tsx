"use client";

import { useCallback, useEffect, useState } from "react";
import { growthApi } from "@/lib/growth-api";
import type { PlannedAction, Week } from "@/lib/types";
import ConflictChoice from "./ConflictChoice";
import PlanForm from "./PlanForm";
import { button, dateLabel, field, Label, Panel, type Target, type Workspace } from "./ui";

const STATUS_LABELS: Record<PlannedAction["status"], string> = {
  planned: "naplánováno",
  in_progress: "rozpracováno",
  done: "dokončeno",
  cancelled: "zrušeno",
};

export default function PlanTab({ ws, target }: { ws: Workspace; target: Target }) {
  const { fail } = ws;
  const [week, setWeek] = useState<Week | null>(null);
  const [weekDate, setWeekDate] = useState("");
  const [editing, setEditing] = useState<PlannedAction | null>(null);

  const loadWeek = useCallback(async (day = "") => {
    setWeek(await growthApi<Week>("/plans" + (day ? `?week_of=${day}` : "")));
  }, []);
  useEffect(() => {
    growthApi<Week>("/plans")
      .then(setWeek)
      .catch(() => fail("Backend neodpovídá. Spusť growthOS a obnov stránku."));
  }, [fail]);

  return (
    <>
      <Panel title="Tento týden">
        <Label title="Zobrazit týden obsahující datum">
          <input
            className={field}
            type="date"
            value={weekDate}
            onChange={(e) => {
              setWeekDate(e.target.value);
              void ws.run(() => loadWeek(e.target.value));
            }}
          />
        </Label>
        {week && (
          <>
            <p className={week.over_budget ? "text-amber-300" : "text-emerald-300"}>
              {week.planned_hours} h naplánováno / {week.budget_hours ?? "nenastavený"} h rozpočet{" "}
              {week.over_budget && "· Plán přesahuje tvou kapacitu"}
            </p>
            {!week.plans.length && (
              <p className="text-zinc-400">
                Tento týden zatím nemá plán. Začni jednou konkrétní akcí.
              </p>
            )}
            <div className="space-y-3">
              {week.plans.map((p) => (
                <article key={p.id} className="rounded-xl border border-white/10 p-4">
                  <div className="flex flex-wrap justify-between gap-2">
                    <h3 className="font-medium">{p.title}</h3>
                    <span className="text-sm text-zinc-400">
                      {p.est_hours} h · {STATUS_LABELS[p.status]}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-zinc-400">
                    {p.starts_at
                      ? dateLabel(p.starts_at) + " — " + dateLabel(p.ends_at!)
                      : "Bez pevného času"}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-sm">{p.description}</p>
                  {p.conflict ? (
                    <div className="mt-3 space-y-2 text-sm text-amber-300">
                      <p>Změny na obou stranách. Vyber, kterou zachovat:</p>
                      <ConflictChoice
                        ws={ws}
                        plan={p}
                        tone="plan"
                        onResolved={() => loadWeek(weekDate)}
                      />
                    </div>
                  ) : (
                    <button className={`${button} mt-3`} onClick={() => setEditing(p)}>
                      Upravit
                    </button>
                  )}
                  {p.target_id && p.status !== "done" && (
                    <a
                      className="ml-3 text-sm text-emerald-300 underline"
                      href={`/growth?tab=complete&target=${p.target_id}&type=${p.target_type}&title=${encodeURIComponent(p.title)}`}
                    >
                      Zapsat výsledek
                    </a>
                  )}
                </article>
              ))}
            </div>
          </>
        )}
      </Panel>
      <Panel title={editing ? "Upravit plán" : "Přidat pracovní blok"}>
        <PlanForm
          key={editing?.id ?? target.id}
          initial={editing ?? undefined}
          target={target}
          onSave={async () => {
            setEditing(null);
            await loadWeek(weekDate);
            ws.notify("Plán uložen. Pro přenos do Google spusť synchronizaci.");
          }}
        />
        {editing && (
          <button className={button} onClick={() => setEditing(null)}>
            Zrušit úpravu
          </button>
        )}
      </Panel>
    </>
  );
}
