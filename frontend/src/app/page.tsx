import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { activateGoal, runSources, undoDecision } from "@/app/actions";
import { GapList } from "@/components/Gaps";
import { HealthBadge } from "@/components/HealthBadge";
import { OpportunityList } from "@/components/Opportunities";
import { RecommendationCard } from "@/components/Recommendation";
import { EmptyState, Section, SectionSkeleton } from "@/components/Section";
import { SubmitButton } from "@/components/SubmitButton";
import { getGaps, getGoals, getRecommendations } from "@/lib/api";

export default function Dashboard({ searchParams }: PageProps<"/">) {
  const kind = searchParams.then((params) =>
    typeof params.kind === "string" ? params.kind : null,
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
        <DashboardContent kind={kind} />
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

async function DashboardContent({ kind }: { kind: Promise<string | null> }) {
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
  const gaps = await getGaps(recommendations.goal_id);
  const { novelty } = recommendations;
  const hidden = recommendations.filtered.filter((f) => f.candidate.decision);

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
        <p className="text-sm text-zinc-400" title="Metrika úspěchu: aspoň 1 nová užitečná věc týdně">
          Za {novelty.window_days} dní:{" "}
          <span className={novelty.new_worthwhile > 0 ? "text-emerald-300" : "text-amber-300"}>
            {novelty.new_worthwhile} nových užitečných
          </span>{" "}
          z {novelty.new_items} nových
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section
          className="lg:col-span-2"
          title="Do next"
          subtitle={`${recommendations.top.length} nejlepších kroků pro „${recommendations.goal_title}“`}
        >
          {recommendations.top.length === 0 ? (
            <EmptyState>Nic k doporučení — načti zdroje nebo uprav profil.</EmptyState>
          ) : (
            <div className="flex flex-col gap-3">
              {recommendations.top.map((item, index) => (
                <RecommendationCard key={item.candidate.key} item={item} rank={index + 1} />
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
                    <form action={undoDecision} className="shrink-0">
                      <input type="hidden" name="target_type" value={f.candidate.source} />
                      <input type="hidden" name="target_id" value={f.candidate.target_id ?? ""} />
                      <SubmitButton className="text-xs text-emerald-300 hover:underline">
                        Vrátit
                      </SubmitButton>
                    </form>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </Section>

        <Section title="Mezery v profilu" subtitle="Pokrytí požadavků cíle, největší mezera nahoře">
          <GapList gaps={gaps} />
        </Section>

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
            kind={await kind}
          />
        </Section>
      </div>
    </>
  );
}
