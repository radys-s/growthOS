"use server";

import { refresh } from "next/cache";

import { api, ApiError } from "@/lib/api";
import type { DecisionStatus, ProfileItemKind } from "@/lib/types";

/** Result shape for forms using useActionState. */
export type ActionState = { ok: boolean; message: string } | null;

const DECISIONS: DecisionStatus[] = [
  "useful",
  "planned",
  "done",
  "skipped",
  "not_interested",
  "already_knew",
];

function text(form: FormData, name: string): string | null {
  const value = form.get(name);
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TARGET_TYPES = ["opportunity", "action"];

/** Ids end up in backend URL paths — accept only real UUIDs (Server Actions are public POSTs). */
function uuid(form: FormData, name: string): string | null {
  const value = text(form, name);
  return value !== null && UUID.test(value) ? value : null;
}

function targetType(form: FormData): string | null {
  const value = text(form, "target_type");
  return value !== null && TARGET_TYPES.includes(value) ? value : null;
}

function int(form: FormData, name: string): number | null {
  const value = text(form, name);
  if (value === null) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function failure(error: unknown): ActionState {
  const message = error instanceof ApiError ? error.message : "Backend neodpovídá";
  return { ok: false, message };
}

// --- dashboard -------------------------------------------------------------------------

export async function decide(form: FormData): Promise<void> {
  const status = text(form, "status") as DecisionStatus | null;
  const type = targetType(form);
  const targetId = uuid(form, "target_id");
  if (!status || !DECISIONS.includes(status) || !type || !targetId) return;
  await api("/decisions", {
    method: "POST",
    body: JSON.stringify({ target_type: type, target_id: targetId, status }),
  });
  refresh();
}

export async function undoDecision(form: FormData): Promise<void> {
  const type = targetType(form);
  const targetId = uuid(form, "target_id");
  if (!type || !targetId) return;
  await api(`/decisions/${type}/${targetId}`, { method: "DELETE" });
  refresh();
}

export async function activateGoal(form: FormData): Promise<void> {
  const goalId = uuid(form, "goal_id");
  if (!goalId) return;
  await api(`/goals/${goalId}`, { method: "PATCH", body: JSON.stringify({ active: true }) });
  refresh();
}

export async function runSources(): Promise<void> {
  // network sources + LLM deadline watcher can take minutes, not the default 5 s
  await api("/sources/run", { method: "POST", signal: AbortSignal.timeout(300_000) });
  refresh();
}

// --- profile ---------------------------------------------------------------------------

export async function saveProfile(_: ActionState, form: FormData): Promise<ActionState> {
  try {
    await api("/profile", {
      method: "PUT",
      body: JSON.stringify({
        name: text(form, "name"),
        birth_date: text(form, "birth_date"),
        country: text(form, "country"),
        education_level: text(form, "education_level"),
        graduation_year: int(form, "graduation_year"),
        max_cost_eur: int(form, "max_cost_eur"),
        weekly_hours_budget: int(form, "weekly_hours_budget"),
      }),
    });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true, message: "Profil uložen" };
}

/** Form fields are named `skill:<signal>` with level 0–4; level 0 removes the skill. */
export async function saveSkills(_: ActionState, form: FormData): Promise<ActionState> {
  const skills: { signal: string; level: number }[] = [];
  for (const [name, value] of form.entries()) {
    if (!name.startsWith("skill:") || typeof value !== "string") continue;
    const level = Number.parseInt(value, 10);
    if (level > 0) skills.push({ signal: name.slice("skill:".length), level });
  }
  try {
    await api("/profile/skills", { method: "PUT", body: JSON.stringify(skills) });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true, message: "Dovednosti uloženy" };
}

export async function addItem(_: ActionState, form: FormData): Promise<ActionState> {
  try {
    await api("/profile/items", {
      method: "POST",
      body: JSON.stringify({
        kind: text(form, "kind") as ProfileItemKind | null,
        title: text(form, "title"),
        result: text(form, "result"),
        url: text(form, "url"),
        signals: form.getAll("signals").filter((s): s is string => typeof s === "string"),
        strength: int(form, "strength") ?? 1,
        achieved_on: text(form, "achieved_on"),
      }),
    });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true, message: "Položka přidána" };
}

export async function deleteItem(form: FormData): Promise<void> {
  const itemId = uuid(form, "item_id");
  if (!itemId) return;
  await api(`/profile/items/${itemId}`, { method: "DELETE" });
  refresh();
}

export async function createGoal(form: FormData): Promise<void> {
  const templateId = text(form, "template_id");
  if (!templateId) return;
  await api("/goals", { method: "POST", body: JSON.stringify({ template_id: templateId }) });
  refresh();
}
