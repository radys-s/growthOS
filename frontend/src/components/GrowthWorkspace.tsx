"use client";

import { useCallback, useMemo, useState } from "react";
import CalendarTab from "./growth/CalendarTab";
import CompleteTab from "./growth/CompleteTab";
import HistoryTab from "./growth/HistoryTab";
import ImportsTab from "./growth/ImportsTab";
import PlanTab from "./growth/PlanTab";
import { button, type Target, type Workspace, type WorkspaceTab } from "./growth/ui";

const TABS: [WorkspaceTab, string][] = [
  ["imports", "Importy"],
  ["plan", "Týdenní plán"],
  ["history", "Historie a progres"],
  ["calendar", "Google kalendář"],
];

export default function GrowthWorkspace({
  initialTab,
  target,
}: {
  initialTab: string;
  target: Target;
}) {
  const [tab, setTab] = useState(initialTab as WorkspaceTab);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const run = useCallback(async (task: () => Promise<void>, onError?: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend neodpovídá.");
      await onError?.().catch(() => {});
    } finally {
      setBusy(false);
    }
  }, []);
  const ws: Workspace = useMemo(
    () => ({ busy, run, notify: setMessage, fail: setError, goTo: setTab }),
    [busy, run],
  );
  // "Zapsat výsledek" is opened from a concrete action, so its tab only exists with a target.
  const tabs: [WorkspaceTab, string][] = target.id
    ? [...TABS, ["complete", "Zapsat výsledek"]]
    : TABS;

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8 sm:px-8">
      <header>
        <p className="text-xs uppercase tracking-widest text-emerald-300">
          growthOS / pracovní prostor
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Od plánu k doloženému výsledku
        </h1>
        <p className="mt-3 text-zinc-400">
          Importuj podklady, vyber práci na tento týden a sleduj, co se opravdu změnilo.
        </p>
      </header>
      <div className="flex flex-wrap gap-2" aria-label="Sekce pracovního prostoru">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            onClick={() => {
              setTab(id);
              setError("");
              setMessage("");
            }}
            aria-pressed={tab === id}
            className={`${button} ${tab === id ? "bg-emerald-400/15" : ""}`}
          >
            {label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="rounded-xl border border-rose-400/30 p-4 text-rose-300">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="rounded-xl border border-emerald-400/30 p-4 text-emerald-200">
          {message}
        </p>
      )}
      {tab === "imports" && <ImportsTab ws={ws} />}
      {tab === "complete" && <CompleteTab ws={ws} target={target} />}
      {tab === "plan" && <PlanTab ws={ws} target={target} />}
      {tab === "history" && <HistoryTab ws={ws} />}
      {tab === "calendar" && <CalendarTab ws={ws} />}
    </main>
  );
}
