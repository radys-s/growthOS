"use client";

import { useCallback, useEffect, useState } from "react";
import { growthApi } from "@/lib/growth-api";
import type { CalendarConnect, CalendarStatus, CalendarSync, PlannedAction } from "@/lib/types";
import ConflictChoice from "./ConflictChoice";
import { button, field, Label, Panel, type Workspace } from "./ui";

const STATE_LABELS: Record<string, string> = {
  connected: "připojeno",
  disconnected: "nepřipojeno",
  needs_calendar: "vytvoř kalendář",
  creation_pending: "vytvoření čeká na ověření",
  reauthorize: "obnov přihlášení",
  calendar_missing: "kalendář chybí",
};

export default function CalendarTab({ ws }: { ws: Workspace }) {
  const { fail } = ws;
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [conflicts, setConflicts] = useState<PlannedAction[]>([]);

  const load = useCallback(async () => {
    const [status, open] = await Promise.all([
      growthApi<CalendarStatus>("/calendar/status"),
      growthApi<PlannedAction[]>("/calendar/conflicts"),
    ]);
    setCalendar(status);
    setConflicts(open);
  }, []);
  useEffect(() => {
    Promise.all([
      growthApi<CalendarStatus>("/calendar/status").then(setCalendar),
      growthApi<PlannedAction[]>("/calendar/conflicts").then(setConflicts),
    ]).catch(() => fail("Backend neodpovídá. Spusť growthOS a obnov stránku."));
  }, [fail]);
  // A failed call may have changed the connection state (e.g. "reauthorize"): reload it.
  const run = (task: () => Promise<void>) => ws.run(task, load);
  const busy = ws.busy;

  return (
    <Panel title="Vyhrazený kalendář growthOS">
      <p className="text-sm text-zinc-400">
        Přenáší pouze naplánované pracovní bloky do kalendáře vytvořeného pro growthOS. Osobní
        kalendáře nečte. Změny se přenesou po spuštění synchronizace.
      </p>
      <p>
        Stav: <strong>{STATE_LABELS[calendar?.state ?? ""] ?? "načítání"}</strong>
      </p>
      {calendar && !calendar.configured && (
        <p className="rounded-lg border border-amber-400/30 p-4 text-sm text-amber-200">
          Připojení zatím není nastavené. Doplň OAuth údaje podle README. Živé propojení bude možné
          ověřit až po přihlášení.
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          className={button}
          disabled={busy || !calendar?.configured}
          onClick={() =>
            run(async () => {
              const result = await growthApi<CalendarConnect>("/calendar/connect", "POST");
              window.location.assign(result.authorization_url);
            })
          }
        >
          Připojit / obnovit Google
        </button>
        <button
          className={button}
          disabled={busy || calendar?.state !== "needs_calendar"}
          onClick={() =>
            run(async () => {
              await growthApi("/calendar/create", "POST");
              await load();
            })
          }
        >
          Vytvořit growthOS kalendář
        </button>
        <button
          className={button}
          disabled={busy || !calendar?.has_calendar}
          onClick={() =>
            run(async () => {
              const result = await growthApi<CalendarSync>("/calendar/sync", "POST");
              await load();
              ws.notify(
                `Synchronizováno ${result.changed} změn; konflikty: ${result.conflicts}. Konflikty vyřešíš níže.` +
                  (result.skipped.length ? ` Přeskočeno: ${result.skipped.join(" ")}` : ""),
              );
            })
          }
        >
          Synchronizovat změny
        </button>
        <button
          className={button}
          disabled={busy || calendar?.state === "disconnected"}
          onClick={() =>
            run(async () => {
              await growthApi("/calendar/disconnect", "POST");
              await load();
              ws.notify("Lokální přihlašovací údaje odstraněny. Události zůstávají v Google.");
            })
          }
        >
          Odpojit
        </button>
      </div>
      {calendar?.state === "creation_pending" && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            void run(async () => {
              await growthApi("/calendar/recover", "POST", {
                calendar_id: form.get("calendar_id"),
              });
              await load();
            });
          }}
        >
          <p className="text-sm text-amber-300">
            Po výpadku mohl kalendář vzniknout. V nastavení Google kalendáře growthOS zkopíruj jeho
            ID. Ověříme označení tohoto připojení, osobní kalendář nepřipojíme.
          </p>
          <Label title="ID vytvořeného growthOS kalendáře">
            <input className={field} name="calendar_id" required />
          </Label>
          <button className={button} disabled={busy}>
            Ověřit a obnovit připojení
          </button>
        </form>
      )}
      {calendar?.state === "calendar_missing" && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await growthApi("/calendar/replace-missing", "POST", { confirmed: true });
              await load();
            });
          }}
        >
          <p className="text-sm text-amber-300">
            Nejdřív zkus původní Google účet. Pokud byl kalendář skutečně smazán, můžeš připravit
            nový; plán a důkazy zůstanou zachované.
          </p>
          <label className="flex gap-2 text-sm">
            <input type="checkbox" required />
            Potvrzuji, že původní kalendář byl odstraněn a chci vytvořit náhradní.
          </label>
          <button className={button} disabled={busy}>
            Připravit náhradní kalendář
          </button>
        </form>
      )}
      {conflicts.map((p) => (
        <div key={p.id} className="space-y-3 rounded-xl border border-amber-400/30 p-4">
          <h3 className="font-medium text-amber-300">Konflikt: {p.title}</h3>
          <ConflictChoice ws={ws} plan={p} onResolved={load} />
        </div>
      ))}
    </Panel>
  );
}
