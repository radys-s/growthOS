import { Suspense } from "react";

import { HealthBadge } from "@/components/HealthBadge";
import { Section } from "@/components/Section";

export default function Dashboard() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-10 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-emerald-400">
            growthOS
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">
            Co mě posune nejvíc?
          </h1>
        </div>
        <Suspense fallback={<span className="text-xs text-zinc-500">Kontroluji API…</span>}>
          <HealthBadge />
        </Suspense>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section
          className="lg:col-span-2"
          title="Do next"
          subtitle="3 nejlepší konkrétní kroky právě teď"
          emptyText="Doporučení se objeví po vytvoření profilu a cíle."
        />
        <Section
          title="Profile gaps"
          subtitle="Co chybí proti cíli"
          emptyText="Zatím není nastavený žádný cíl."
        />
        <Section
          className="lg:col-span-3"
          title="Opportunities"
          subtitle="Aktuální relevantní příležitosti"
          emptyText="Zatím nejsou připojené žádné zdroje."
        />
      </div>
    </main>
  );
}
