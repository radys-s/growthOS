"use client";

import { growthApi } from "@/lib/growth-api";
import EvidenceForm from "./EvidenceForm";
import { emptyItem, Panel, type Target, type Workspace } from "./ui";

export default function CompleteTab({ ws, target }: { ws: Workspace; target: Target }) {
  return (
    <Panel title="Zapsat dokončený výsledek">
      {target.id ? (
        <EvidenceForm
          initial={{ ...emptyItem, title: target.title }}
          completion
          onSave={async (item) => {
            await growthApi("/completions", "POST", {
              target_type: target.type,
              target_id: target.id,
              item,
              evidence_kind: "demonstrated",
              confirmed: true,
            });
            ws.goTo("history");
            ws.notify("Výsledek je potvrzený. Profil, mezery a doporučení se přepočítaly.");
          }}
        />
      ) : (
        <p>Vyber akci na dashboardu a otevři „Zapsat výsledek“.</p>
      )}
    </Panel>
  );
}
