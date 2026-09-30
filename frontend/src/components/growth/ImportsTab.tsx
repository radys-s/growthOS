"use client";

import { useEffect, useState, type FormEvent } from "react";
import { growthApi } from "@/lib/growth-api";
import { PROPOSAL_SOURCE_LABELS } from "@/lib/labels";
import type { ImportProposal, ProfileItem } from "@/lib/types";
import EvidenceForm from "./EvidenceForm";
import { button, field, Label, Panel, type Workspace } from "./ui";

export default function ImportsTab({ ws }: { ws: Workspace }) {
  const [proposals, setProposals] = useState<ImportProposal[]>([]);
  const [active, setActive] = useState<ImportProposal | null>(null);
  const { fail } = ws;

  // Proposals waiting from earlier imports or found in labelled Gmail messages.
  useEffect(() => {
    growthApi<ImportProposal[]>("/imports")
      .then(setProposals)
      .catch(() => fail("Backend neodpovídá. Spusť growthOS a obnov stránku."));
  }, [fail]);

  async function preview(event: FormEvent<HTMLFormElement>, kind: "text" | "file" | "github") {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await ws.run(async () => {
      const body =
        kind === "file"
          ? form
          : kind === "text"
            ? { text: form.get("text") }
            : { repository: form.get("repository") };
      const rows = await growthApi<ImportProposal[]>(`/imports/${kind}`, "POST", body);
      const fresh = new Set(rows.map((r) => r.id));
      setProposals((old) => [...rows, ...old.filter((p) => !fresh.has(p.id))]);
      setActive(null);
      ws.notify(`${rows.length} návrhů k posouzení. Profil se zatím nezměnil.`);
    });
  }

  return (
    <>
      <Panel title="Podklady zůstávají lokálně">
        <p className="text-sm text-zinc-400">
          CV ani obsah repozitáře neposíláme AI. Návrhy můžeš upravit a potvrdit jednotlivě; původní
          profil zůstane zachován.
        </p>
        <form onSubmit={(e) => preview(e, "text")} className="space-y-3">
          <Label title="Text CV">
            <textarea name="text" className={field} rows={5} maxLength={100000} required />
          </Label>
          <button disabled={ws.busy} className={button}>
            Připravit návrhy z textu
          </button>
        </form>
        <div className="grid gap-6 border-t border-white/10 pt-5 sm:grid-cols-2">
          <form onSubmit={(e) => preview(e, "file")} className="space-y-3">
            <Label title="PDF nebo DOCX (nejvýše 5 MB)">
              <input className={field} name="file" type="file" accept=".pdf,.docx" required />
            </Label>
            <p className="text-xs text-zinc-400">Pro naskenované PDF vlož text ručně.</p>
            <button className={button} disabled={ws.busy}>
              Načíst soubor
            </button>
          </form>
          <form onSubmit={(e) => preview(e, "github")} className="space-y-3">
            <Label title="Veřejný GitHub repozitář">
              <input
                className={field}
                name="repository"
                placeholder="vlastník/repozitář"
                required
              />
            </Label>
            <p className="text-xs text-zinc-400">
              Čteme metadata, README a závislosti. Kód nespouštíme.
            </p>
            <button className={button} disabled={ws.busy}>
              Analyzovat repozitář
            </button>
          </form>
        </div>
      </Panel>
      {proposals.length > 0 && (
        <Panel title="Návrhy k potvrzení">
          <div className="grid gap-2">
            {proposals.map((p) => (
              <button
                className="rounded-lg border border-white/10 p-3 text-left hover:bg-white/5 disabled:opacity-50"
                key={p.id}
                disabled={!!p.confirmed_item_id}
                onClick={() => setActive(p)}
              >
                <span className="mr-2 rounded bg-white/10 px-1.5 py-0.5 text-xs text-zinc-300">
                  {PROPOSAL_SOURCE_LABELS[p.source] ?? p.source}
                </span>
                {p.proposed.title}
                <span className="ml-2 text-xs text-zinc-400">
                  {p.confirmed_item_id ? "Potvrzeno" : "Posoudit →"}
                </span>
              </button>
            ))}
          </div>
        </Panel>
      )}
      {active && (
        <Panel title="Posoudit návrh">
          <EvidenceForm
            key={active.id}
            initial={active.proposed}
            source={active}
            onSave={async (item, kind) => {
              const saved = await growthApi<ProfileItem>(`/imports/${active.id}/confirm`, "POST", {
                item,
                evidence_kind: kind,
                confirmed: true,
              });
              setProposals((rows) =>
                rows.map((p) => (p.id === active.id ? { ...p, confirmed_item_id: saved.id } : p)),
              );
              setActive(null);
              ws.notify("Potvrzeno. Existující záznamy zůstaly zachovány.");
            }}
          />
        </Panel>
      )}
    </>
  );
}
