"use client";

import { useCallback, useEffect, useState } from "react";
import { growthApi } from "@/lib/growth-api";
import type { GmailConnect, GmailStatus, SourceReport } from "@/lib/types";
import { button, Panel, type Workspace } from "./ui";

const STATE_LABELS: Record<string, string> = {
  connected: "připojeno",
  disconnected: "nepřipojeno",
  reauthorize: "obnov přihlášení",
};

export default function GmailTab({ ws }: { ws: Workspace }) {
  const { fail } = ws;
  const [gmail, setGmail] = useState<GmailStatus | null>(null);

  const load = useCallback(async () => {
    setGmail(await growthApi<GmailStatus>("/gmail/status"));
  }, []);
  useEffect(() => {
    growthApi<GmailStatus>("/gmail/status")
      .then(setGmail)
      .catch(() => fail("Backend neodpovídá. Spusť growthOS a obnov stránku."));
  }, [fail]);
  // A failed call may have changed the connection state (e.g. "reauthorize"): reload it.
  const run = (task: () => Promise<void>) => ws.run(task, load);
  const busy = ws.busy;
  const ready = gmail?.state === "connected" && gmail.llm_configured && gmail.enabled;

  return (
    <Panel title="Gmail jen se štítkem">
      <p className="text-sm text-zinc-400">
        growthOS čte pouze zprávy se štítkem <strong>{gmail?.label ?? "growthOS"}</strong> z
        posledního roku, bez příloh. Nic neodesílá ani nemaže. Štítek nastav ručně nebo filtrem v
        Gmailu.
      </p>
      <p className="rounded-lg border border-amber-400/30 p-4 text-sm text-amber-200">
        Text označených zpráv (nejvýše 12 000 znaků) se posílá tvému LLM (OmniRoute). Uložíme jen
        ověřené citace a odkaz na zprávu. Příležitosti bez doslovné citace zahodíme a úspěchy čekají
        na tvé potvrzení v Importech.
      </p>
      <p>
        Stav: <strong>{STATE_LABELS[gmail?.state ?? ""] ?? "načítání"}</strong>
        {gmail && ` · zpracováno zpráv: ${gmail.processed}`}
      </p>
      {gmail && !gmail.configured && (
        <p className="text-sm text-amber-200">
          Doplň GOOGLE_CLIENT_ID a GOOGLE_CLIENT_SECRET podle README a zaregistruj redirect URI
          Gmailu.
        </p>
      )}
      {gmail && !gmail.llm_configured && (
        <p className="text-sm text-amber-200">Bez LLM_BASE_URL (OmniRoute) se zprávy nečtou.</p>
      )}
      {gmail && !gmail.enabled && (
        <p className="text-sm text-amber-200">Přidej „gmail“ do SOURCES_ENABLED v backend/.env.</p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          className={button}
          disabled={busy || !gmail?.configured}
          onClick={() =>
            run(async () => {
              const result = await growthApi<GmailConnect>("/gmail/connect", "POST");
              window.location.assign(result.authorization_url);
            })
          }
        >
          Připojit / obnovit Gmail
        </button>
        <button
          className={button}
          disabled={busy || !ready}
          onClick={() =>
            run(async () => {
              const report = await growthApi<SourceReport>("/gmail/run", "POST");
              await load();
              if (report.status === "error") throw new Error(report.error ?? "Čtení selhalo.");
              ws.notify(
                `Přečteno nových zpráv: ${report.fetched}; nové příležitosti: ${report.result?.created ?? 0}, doplněné termíny: ${report.result?.updated ?? 0}. Úspěchy najdeš v Importech.` +
                  (report.error ? ` Některé zprávy se zkusí znovu: ${report.error}` : ""),
              );
            })
          }
        >
          Načíst označené zprávy
        </button>
        <button
          className={button}
          disabled={busy || gmail?.state === "disconnected"}
          onClick={() =>
            run(async () => {
              await growthApi("/gmail/disconnect", "POST");
              await load();
              ws.notify(
                "Lokální přihlašovací údaje odstraněny. Přístup můžeš zrušit i v Google účtu.",
              );
            })
          }
        >
          Odpojit
        </button>
      </div>
    </Panel>
  );
}
