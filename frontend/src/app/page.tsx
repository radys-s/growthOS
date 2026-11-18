import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { activateGoal, runSources, undoDecision } from "@/app/actions";
import { GapList } from "@/components/Gaps";
import { HealthBadge } from "@/components/HealthBadge";
import { OpportunityList } from "@/components/Opportunities";
import { RecommendationCard } from "@/components/Recommendation";
import { EmptyState, Section, SectionSkeleton } from "@/components/Section";
import { SourceList } from "@/components/Sources";
import { SubmitButton } from "@/components/SubmitButton";
import { getGaps, getGoals, getRecommendations, getSources } from "@/lib/api";
import type { Candidate } from "@/lib/types";

/** Confirmation shown after a decision, phrased as what just happened. */
const DECIDED_TEXT: Record<string, string> = {
  useful: "Označeno jako užitečné",
  skipped: "Přeskočeno",
  not_interested: "Skryto, nezajímá tě",
  already_knew: "Označeno jako už známé",
  planned: "Naplánováno",
  done: "Hotovo",
};

export default function Dashboard({ searchParams }: PageProps<"/">) {
  const kind = searchParams.then((params) =>
    typeof params.kind === "string" ? params.kind : null,
  );
  const decided = searchParams.then((params) =>
    typeof params.decided === "string" ? params.decided : null,
  );
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
        <div className="flex items-center gap-3">
          <Link
            href="/profile"
            className="rounded-full border border-white/10 px-3 py-1 text-xs text-zinc-300 hover:bg-white/5"
          >
            Profil a cíle
          </Link>
          <Suspense fallback={<span className="text-xs text-zinc-500">Kontroluji API…</span>}>
            <HealthBadge />
          </Suspense>
        </div>
      </header>

      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent kind={kind} decided={decided} />
      </Suspense>
    </main>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Section className="lg:col-span-2" title="Do next">
        <SectionSkeleton rows={3} />
      </Section>
      <Section title="Mezery v profilu">
        <SectionSkeleton rows={4} />
      </Section>
    </div>
  );
}

function UndoForm({
  candidate,
  kind,
  className,
}: {
  candidate: Candidate;
  kind: string | null;
  className: string;
}) {
  return (
    <form action={undoDecision} className="shrink-0">
      <input type="hidden" name="target_type" value={candidate.source} />
      <input type="hidden" name="target_id" value={candidate.target_id ?? ""} />
      {kind && <input type="hidden" name="kind" value={kind} />}
      <SubmitButton className={className}>Vrátit</SubmitButton>
    </form>
  );
}

async function DashboardContent({
  kind: kindParam,
  decided: decidedParam,
}: {
  kind: Promise<string | null>;
  decided: Promise<string | null>;
}) {
  await connection();
  let goals, recommendations;
  try {
    [goals, recommendations] = await Promise.all([getGoals(), getRecommendations()]);
  } catch {
    return (
      <EmptyState>
        Backend neodpovídá. Spusť ho v <code>backend/</code>:{" "}
        <code>uv run python -m uvicorn app.main:app --reload</code>
      </EmptyState>
    );
  }
  if (!recommendations) {
    return (
      <EmptyState>
        Zatím nemáš aktivní cíl.{" "}
        <Link href="/profile" className="text-emerald-300 underline">
          Vyber si ho v profilu
        </Link>
        .
      </EmptyState>
    );
  }
  const [gaps, sources] = await Promise.all([
    getGaps(recommendations.goal_id),
    getSources().catch(() => null), // the panel is optional; never break the dashboard
  ]);
  const { novelty } = recommendations;
  const hidden = recommendations.filtered.filter((f) => f.candidate.decision);
  const [kind, decidedKey] = await Promise.all([kindParam, decidedParam]);
  const decided = [...recommendations.ranked, ...recommendations.filtered].find(
    (i) => i.candidate.key === decidedKey && i.candidate.decision,
  )?.candidate;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-zinc-900/40 px-5 py-3">
        <nav className="flex flex-wrap items-center gap-2" aria-label="Cíl">
          <span className="text-xs uppercase tracking-wider text-zinc-500">Cíl</span>
          {goals.map((goal) =>
            goal.active ? (
              <span
                key={goal.id}
                className="rounded-full bg-emerald-400/15 px-3 py-1 text-sm font-medium text-emerald-200"
              >
                {goal.title}
              </span>
            ) : (
              <form key={goal.id} action={activateGoal}>
                <input type="hidden" name="goal_id" value={goal.id} />
                <SubmitButton className="rounded-full border border-white/10 px-3 py-1 text-sm text-zinc-400 hover:bg-white/5 hover:text-zinc-200">
                  {goal.title}
                </SubmitButton>
              </form>
            ),
          )}
        </nav>
        <p
          className="text-sm text-zinc-400"
          title="Nově objevené položky a tvé výslovné hodnocení"
        >
          Za {novelty.window_days} dní:{" "}
          <span className={novelty.explicitly_useful > 0 ? "text-emerald-300" : "text-amber-300"}>
            {novelty.explicitly_useful} označených jako užitečné
          </span>{" "}
          · {novelty.newly_discovered} nově objevených
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section
          className="lg:col-span-2"
          title="Do next"
          subtitle={`${recommendations.top.length} nejlepších kroků pro „${recommendations.goal_title}“`}
        >
          {decided && (
            <div
              role="status"
              className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-400/30 bg-emerald-400/5 px-4 py-3 text-sm text-zinc-200"
            >
              <span>
                {DECIDED_TEXT[decided.decision!] ?? decided.decision}: „{decided.title}“
              </span>
              <UndoForm
                candidate={decided}
                kind={kind}
                className="rounded-md border border-emerald-400/40 px-3 py-1.5 text-emerald-200 hover:bg-emerald-400/10"
              />
            </div>
          )}
          {recommendations.top.length === 0 ? (
            <EmptyState>Nic k doporučení — načti zdroje nebo uprav profil.</EmptyState>
          ) : (
            <div className="flex flex-col gap-3">
              {recommendations.top.map((item, index) => (
                <RecommendationCard
                  key={item.candidate.key}
                  item={item}
                  rank={index + 1}
                  kind={kind}
                />
              ))}
            </div>
          )}
          {hidden.length > 0 && (
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer text-zinc-500 hover:text-zinc-300">
                Rozhodnuté a skryté ({hidden.length})
              </summary>
              <ul className="mt-2 space-y-1 text-zinc-400">
                {hidden.map((f) => (
                  <li key={f.candidate.key} className="flex items-baseline justify-between gap-3">
                    <span>
                      {f.candidate.title} — <span className="text-zinc-500">{f.reason}</span>
                    </span>
                    <UndoForm
                      candidate={f.candidate}
                      kind={kind}
                      className="text-xs text-emerald-300 hover:underline"
                    />
                  </li>
                ))}
              </ul>
            </details>
          )}
        </Section>

        <div className="flex flex-col gap-6">
          <Section
            title="Mezery v profilu"
            subtitle="Pokrytí požadavků cíle, největší mezera nahoře"
          >
            <GapList gaps={gaps} />
          </Section>
          {sources && (
            <Section
              title="Zdroje"
              subtitle="Odkud příležitosti pocházejí a kdy se naposledy načetly"
            >
              <SourceList sources={sources} />
            </Section>
          )}
        </div>

        <Section
          className="lg:col-span-3"
          title="Příležitosti"
          subtitle="Seřazené podle priority pro aktivní cíl"
          action={
            <form action={runSources}>
              <SubmitButton className="rounded-md border border-white/10 px-3 py-1 text-xs text-zinc-300 hover:bg-white/5">
                Načíst zdroje
              </SubmitButton>
            </form>
          }
        >
          <OpportunityList
            ranked={recommendations.ranked}
            filtered={recommendations.filtered}
            kind={kind}
          />
        </Section>
      </div>
    </>
  );
}
