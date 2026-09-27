import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { activateGoal, createGoal, deleteItem } from "@/app/actions";
import { AddItemForm, ProfileForm, SkillsForm } from "@/components/ProfileForms";
import { Badge } from "@/components/Recommendation";
import { EmptyState, Section, SectionSkeleton } from "@/components/Section";
import { SubmitButton } from "@/components/SubmitButton";
import { getGoals, getGoalTemplates, getProfile, getTaxonomy } from "@/lib/api";
import { ITEM_KIND_LABELS } from "@/lib/labels";

export const metadata: Metadata = { title: "Profil · growthOS" };

export default function ProfilePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-10 sm:px-8">
      <header>
        <Link href="/" className="text-xs text-zinc-400 hover:text-zinc-200">
          ← Zpět na dashboard
        </Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-50">Profil a cíle</h1>
        <p className="text-sm text-zinc-400">
          Z toho, co tu vyplníš, se počítají mezery a pořadí doporučení.
        </p>
      </header>
      <Suspense fallback={<SectionSkeleton rows={4} />}>
        <ProfileContent />
      </Suspense>
    </main>
  );
}

async function ProfileContent() {
  await connection();
  let data;
  try {
    data = await Promise.all([getProfile(), getTaxonomy(), getGoals(), getGoalTemplates()]);
  } catch {
    return <EmptyState>Backend neodpovídá.</EmptyState>;
  }
  const [profile, taxonomy, goals, templates] = data;
  const labels = new Map(taxonomy.map((s) => [s.id, s.label]));
  const unusedTemplates = templates.filter((t) => !goals.some((g) => g.template_id === t.id));

  return (
    <>
      <Section title="Cíle" subtitle="Aktivní cíl určuje váhy a požadované signály rankingu">
        <ul className="flex flex-col gap-2">
          {goals.map((goal) => (
            <li
              key={goal.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 px-4 py-3"
            >
              <div>
                <p className="font-medium text-zinc-100">{goal.title}</p>
                <p className="text-xs text-zinc-500">
                  {goal.required_signals.length} požadovaných signálů
                </p>
              </div>
              {goal.active ? (
                <Badge tone="emerald">Aktivní</Badge>
              ) : (
                <form action={activateGoal}>
                  <input type="hidden" name="goal_id" value={goal.id} />
                  <SubmitButton className="rounded-md border border-white/10 px-3 py-1 text-xs text-zinc-300 hover:bg-white/5">
                    Nastavit jako aktivní
                  </SubmitButton>
                </form>
              )}
            </li>
          ))}
        </ul>
        {unusedTemplates.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {unusedTemplates.map((template) => (
              <form key={template.id} action={createGoal}>
                <input type="hidden" name="template_id" value={template.id} />
                <SubmitButton className="rounded-md border border-dashed border-white/20 px-3 py-1 text-xs text-zinc-300 hover:bg-white/5">
                  + {template.title}
                </SubmitButton>
              </form>
            ))}
          </div>
        )}
      </Section>

      <Section title="Základní údaje" subtitle="Věk, země a vzdělání se používají pro podmínky účasti">
        <ProfileForm profile={profile} />
      </Section>

      <Section title="Dovednosti" subtitle="0 = nemám · 4 = expert. Pokrytí signálu = úroveň / 4.">
        <SkillsForm profile={profile} signals={taxonomy} />
      </Section>

      <Section
        title="Důkazy"
        subtitle="Projekty, soutěže a výsledky — dokládají signály silněji než samotná dovednost"
      >
        {profile.items.length === 0 ? (
          <EmptyState>Zatím žádné položky.</EmptyState>
        ) : (
          <ul className="mb-6 flex flex-col gap-2">
            {profile.items.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-white/10 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="font-medium text-zinc-100">
                    {item.title}
                    {item.result && <span className="text-zinc-400"> · {item.result}</span>}
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Badge>{ITEM_KIND_LABELS[item.kind]}</Badge>
                    <Badge tone="emerald">síla {item.strength}/4</Badge>
                    {item.signals.map((s) => (
                      <Badge key={s} tone="sky">
                        {labels.get(s) ?? s}
                      </Badge>
                    ))}
                  </div>
                </div>
                <form action={deleteItem}>
                  <input type="hidden" name="item_id" value={item.id} />
                  <SubmitButton className="text-xs text-zinc-500 hover:text-rose-300">
                    Odebrat
                  </SubmitButton>
                </form>
              </li>
            ))}
          </ul>
        )}
        <details className="rounded-lg border border-white/10 px-4 py-3">
          <summary className="cursor-pointer text-sm text-zinc-300">+ Přidat důkaz</summary>
          <div className="mt-4">
            <AddItemForm signals={taxonomy} />
          </div>
        </details>
      </Section>
    </>
  );
}
