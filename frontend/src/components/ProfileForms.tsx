"use client";

import { useActionState } from "react";

import { type ActionState, addItem, saveProfile, saveSkills } from "@/app/actions";
import { SubmitButton } from "@/components/SubmitButton";
import { EDUCATION_LABELS, ITEM_KIND_LABELS, LEVEL_LABELS } from "@/lib/labels";
import type { Profile, Signal } from "@/lib/types";

const input =
  "w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-1.5 text-sm text-zinc-100 outline-none focus:border-emerald-400/50";
const label = "flex flex-col gap-1 text-xs text-zinc-400";
const primary =
  "rounded-md bg-emerald-500/90 px-4 py-1.5 text-sm font-medium text-zinc-950 hover:bg-emerald-400";

function Message({ state }: { state: ActionState }) {
  if (!state) return null;
  return (
    <p role="status" className={`text-sm ${state.ok ? "text-emerald-300" : "text-rose-300"}`}>
      {state.message}
    </p>
  );
}

export function ProfileForm({ profile }: { profile: Profile }) {
  const [state, action] = useActionState(saveProfile, null);
  return (
    <form action={action} className="grid gap-4 sm:grid-cols-2">
      <label className={label}>
        Jméno
        <input name="name" required defaultValue={profile.name} className={input} />
      </label>
      <label className={label}>
        Datum narození (pro věkové podmínky)
        <input
          name="birth_date"
          type="date"
          defaultValue={profile.birth_date ?? ""}
          className={input}
        />
      </label>
      <label className={label}>
        Země (ISO kód)
        <input
          name="country"
          required
          minLength={2}
          maxLength={2}
          defaultValue={profile.country}
          className={`${input} uppercase`}
        />
      </label>
      <label className={label}>
        Vzdělání
        <select name="education_level" defaultValue={profile.education_level} className={input}>
          {Object.entries(EDUCATION_LABELS).map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </select>
      </label>
      <label className={label}>
        Rok maturity / absolvování
        <input
          name="graduation_year"
          type="number"
          min={2000}
          max={2100}
          defaultValue={profile.graduation_year ?? ""}
          className={input}
        />
      </label>
      <label className={label}>
        Hodin týdně na růst
        <input
          name="weekly_hours_budget"
          type="number"
          min={1}
          max={80}
          defaultValue={profile.weekly_hours_budget ?? ""}
          className={input}
        />
      </label>
      <label className={label}>
        Max. cena za příležitost (€, prázdné = bez limitu)
        <input
          name="max_cost_eur"
          type="number"
          min={0}
          defaultValue={profile.max_cost_eur ?? ""}
          className={input}
        />
      </label>
      <div className="flex items-end gap-3">
        <SubmitButton className={primary}>Uložit profil</SubmitButton>
        <Message state={state} />
      </div>
    </form>
  );
}

export function SkillsForm({ profile, signals }: { profile: Profile; signals: Signal[] }) {
  const [state, action] = useActionState(saveSkills, null);
  const levels = new Map(profile.skills.map((s) => [s.signal, s.level]));
  const skills = signals.filter((s) => s.category === "skill");
  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {skills.map((signal) => (
          <label
            key={signal.id}
            className="flex items-center justify-between gap-3 text-sm text-zinc-200"
          >
            <span className="truncate">{signal.label}</span>
            <select
              name={`skill:${signal.id}`}
              defaultValue={levels.get(signal.id) ?? 0}
              className={`${input} w-32 shrink-0`}
            >
              {LEVEL_LABELS.map((text, level) => (
                <option key={level} value={level}>
                  {level} · {text}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <SubmitButton className={primary}>Uložit dovednosti</SubmitButton>
        <Message state={state} />
      </div>
    </form>
  );
}

export function AddItemForm({ signals }: { signals: Signal[] }) {
  const [state, action] = useActionState(addItem, null);
  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={label}>
          Název
          <input name="title" required className={input} />
        </label>
        <label className={label}>
          Druh
          <select name="kind" className={input}>
            {Object.entries(ITEM_KIND_LABELS).map(([value, text]) => (
              <option key={value} value={value}>
                {text}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          Výsledek (např. „81. z 5000“)
          <input name="result" className={input} />
        </label>
        <label className={label}>
          Odkaz
          <input name="url" type="url" className={input} />
        </label>
        <label className={label}>
          Síla důkazu (1 slabý – 4 top)
          <select name="strength" defaultValue={2} className={input}>
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          Kdy
          <input name="achieved_on" type="date" className={input} />
        </label>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-xs text-zinc-400">Co to dokládá</legend>
        <div className="flex flex-wrap gap-2">
          {signals.map((signal) => (
            <label
              key={signal.id}
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-xs text-zinc-300 has-[:checked]:border-emerald-400/50 has-[:checked]:bg-emerald-400/10 has-[:checked]:text-emerald-200"
            >
              <input type="checkbox" name="signals" value={signal.id} className="sr-only" />
              {signal.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex items-center gap-3">
        <SubmitButton className={primary}>Přidat</SubmitButton>
        <Message state={state} />
      </div>
    </form>
  );
}
