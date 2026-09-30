"use client";

import { useState, type FormEvent } from "react";
import { growthApi } from "@/lib/growth-api";
import { localInput, pragueTime } from "@/lib/prague-time";
import type { PlannedAction, PlanInput } from "@/lib/types";
import { button, field, Label } from "./ui";

export default function PlanForm({
  initial,
  target,
  onSave,
}: {
  initial?: PlannedAction;
  target: { id: string; type: "action" | "opportunity"; title: string };
  onSave: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const data: PlanInput = {
        title: String(f.get("title")),
        description: String(f.get("description")),
        est_hours: Number(f.get("hours")),
        week_of: String(f.get("week")),
        status: String(f.get("status")) as PlanInput["status"],
        target_id: initial?.target_id ?? (target.id || null),
        target_type: initial?.target_type ?? (target.id ? target.type : null),
        starts_at: pragueTime(String(f.get("start")), String(f.get("offset"))),
        ends_at: pragueTime(String(f.get("end")), String(f.get("offset"))),
      };
      await growthApi(initial ? `/plans/${initial.id}` : "/plans", initial ? "PUT" : "POST", data);
      await onSave();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Uložení selhalo.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <Label title="Akce">
        <input
          className={field}
          name="title"
          required
          maxLength={300}
          defaultValue={initial?.title ?? target.title}
        />
      </Label>
      <Label title="Poznámka">
        <textarea className={field} name="description" defaultValue={initial?.description ?? ""} />
      </Label>
      <div className="grid gap-4 sm:grid-cols-3">
        <Label title="Odhad práce (hodiny)">
          <input
            className={field}
            name="hours"
            type="number"
            min="0.25"
            max="168"
            step="0.25"
            defaultValue={initial?.est_hours ?? 2}
            required
          />
        </Label>
        <Label title="Den v plánovaném týdnu">
          <input
            className={field}
            type="date"
            name="week"
            defaultValue={initial?.week_of ?? new Date().toLocaleDateString("en-CA")}
            required
          />
        </Label>
        <Label title="Stav">
          <select className={field} name="status" defaultValue={initial?.status ?? "planned"}>
            <option value="planned">Naplánováno</option>
            <option value="in_progress">Rozpracováno</option>
            <option value="done">Dokončeno (bez přidání důkazu)</option>
            <option value="cancelled">Zrušeno</option>
          </select>
        </Label>
      </div>
      <p className="text-sm text-zinc-400">
        Čas je volitelný, v pásmu Praha. Vyplněním vytváříš vlastní pracovní blok; odhadované
        deadliny se nepřenášejí.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label title="Začátek">
          <input
            className={field}
            type="datetime-local"
            name="start"
            defaultValue={localInput(initial?.starts_at ?? null)}
          />
        </Label>
        <Label title="Konec">
          <input
            className={field}
            type="datetime-local"
            name="end"
            defaultValue={localInput(initial?.ends_at ?? null)}
          />
        </Label>
      </div>
      <Label title="Při podzimní změně času">
        <select className={field} name="offset" defaultValue="">
          <option value="">Automaticky, pokud je čas jednoznačný</option>
          <option value="+02:00">První výskyt · letní čas</option>
          <option value="+01:00">Druhý výskyt · zimní čas</option>
        </select>
      </Label>
      {error && (
        <p role="alert" className="text-rose-300">
          {error}
        </p>
      )}
      <button disabled={busy} className={button}>
        {busy ? "Ukládám…" : "Uložit plán"}
      </button>
    </form>
  );
}
