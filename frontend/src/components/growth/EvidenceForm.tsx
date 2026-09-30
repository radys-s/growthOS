"use client";

import { useEffect, useState, type FormEvent } from "react";
import { growthApi } from "@/lib/growth-api";
import type { ImportProposal, ItemInput, Signal } from "@/lib/types";
import { button, field, Label } from "./ui";

export default function EvidenceForm({
  initial,
  source,
  completion,
  onSave,
}: {
  initial: ItemInput;
  source?: ImportProposal;
  completion?: boolean;
  onSave: (item: ItemInput, kind: "claimed" | "demonstrated") => Promise<void>;
}) {
  const [item, setItem] = useState(initial);
  const [kind, setKind] = useState<"claimed" | "demonstrated">(
    completion ? "demonstrated" : "claimed",
  );
  const [signals, setSignals] = useState<Signal[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    growthApi<Signal[]>("/taxonomy")
      .then(setSignals)
      .catch(() => setError("Nelze načíst dovednosti. Zkus stránku obnovit."));
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(item, kind);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Uložení selhalo.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      {source && (
        <details className="rounded-lg bg-black/20 p-3 text-sm">
          <summary className="cursor-pointer text-emerald-300">
            Původní zdroj: {source.reference}
          </summary>
          <pre className="mt-3 max-h-60 overflow-auto whitespace-pre-wrap font-sans text-zinc-400">
            {source.excerpt}
          </pre>
        </details>
      )}
      <Label title="Název">
        <input
          required
          maxLength={300}
          className={field}
          value={item.title}
          onChange={(e) => setItem({ ...item, title: e.target.value })}
        />
      </Label>
      <Label title="Popis">
        <textarea
          className={field}
          rows={3}
          value={item.description ?? ""}
          onChange={(e) => setItem({ ...item, description: e.target.value })}
        />
      </Label>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label title="Druh výsledku">
          <select
            className={field}
            value={item.kind}
            onChange={(e) => setItem({ ...item, kind: e.target.value as ItemInput["kind"] })}
          >
            <option value="project">Projekt</option>
            <option value="competition">Soutěž</option>
            <option value="achievement">Úspěch</option>
            <option value="certification">Certifikace</option>
            <option value="experience">Zkušenost</option>
            <option value="publication">Publikace</option>
          </select>
        </Label>
        <Label title="Co tento záznam představuje">
          <select
            className={field}
            disabled={completion}
            value={kind}
            onChange={(e) => setKind(e.target.value as typeof kind)}
          >
            <option value="claimed">Tvrzení / zájem (nemění pokrytí)</option>
            <option value="demonstrated">Konkrétní doložený výsledek</option>
          </select>
        </Label>
      </div>
      <p className="text-xs text-zinc-400">
        README ani seznam knihoven nedokazují zvládnutí technologie. Doložený výsledek potvrď jen
        podle toho, co jsi skutečně dokončil.
      </p>
      <Label title="Konkrétní výsledek">
        <input
          className={field}
          maxLength={200}
          required={kind === "demonstrated"}
          value={item.result ?? ""}
          onChange={(e) => setItem({ ...item, result: e.target.value })}
          placeholder="Co vzniklo, jak jsi ověřil funkčnost, jaký byl výsledek?"
        />
      </Label>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label title="Datum výsledku">
          <input
            type="date"
            required={completion}
            className={field}
            value={item.achieved_on ?? ""}
            onChange={(e) => setItem({ ...item, achieved_on: e.target.value || null })}
          />
        </Label>
        <Label title="Síla důkazu (0–4)">
          <select
            className={field}
            value={item.strength}
            onChange={(e) => setItem({ ...item, strength: Number(e.target.value) })}
          >
            <option value={0}>0 · Bez prokázaného výsledku</option>
            <option value={1}>1 · První praktický výsledek</option>
            <option value={2}>2 · Samostatně dokončeno</option>
            <option value={3}>3 · Silný ověřený výsledek</option>
            <option value={4}>4 · Výjimečný, opakovaně doložený</option>
          </select>
        </Label>
      </div>
      <p className="text-xs text-zinc-400">
        Pokrytí cíle se zvýší jen tehdy, když je tento potvrzený důkaz silnější než už zaznamenaná
        dovednost nebo výsledek pro stejný signál.
      </p>
      <Label title="Odkaz na důkaz (volitelné)">
        <input
          type="url"
          className={field}
          value={item.url ?? ""}
          onChange={(e) => setItem({ ...item, url: e.target.value || null })}
        />
      </Label>
      <fieldset className="rounded-lg border border-white/10 p-3">
        <legend className="px-1 text-sm">Co výsledek dokládá</legend>
        <div className="grid max-h-48 gap-2 overflow-auto sm:grid-cols-2">
          {signals.map((signal) => (
            <label key={signal.id} className="flex items-center gap-2 text-xs text-zinc-300">
              <input
                type="checkbox"
                checked={item.signals.includes(signal.id)}
                onChange={(e) =>
                  setItem({
                    ...item,
                    signals: e.target.checked
                      ? [...item.signals, signal.id]
                      : item.signals.filter((s) => s !== signal.id),
                  })
                }
              />
              {signal.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="flex gap-2 text-sm">
        <input required type="checkbox" />
        Potvrzuji správnost údajů a chci je přidat do profilu.
      </label>
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      <button className={button} disabled={busy || !signals.length}>
        {busy ? "Ukládám…" : "Potvrdit a přidat do profilu"}
      </button>
    </form>
  );
}
