import type { ReactNode } from "react";
import type { ItemInput } from "@/lib/types";

export const field =
  "w-full rounded-lg border border-white/15 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-400 focus:outline-none";
export const button =
  "rounded-lg border border-emerald-400/30 px-4 py-2 text-sm text-emerald-200 transition-colors hover:bg-emerald-400/10 disabled:opacity-50";
export const emptyItem: ItemInput = {
  kind: "project",
  title: "",
  description: "",
  result: "",
  url: null,
  signals: [],
  strength: 1,
  achieved_on: null,
};

export type WorkspaceTab = "imports" | "complete" | "plan" | "history" | "calendar";

/** Shared busy / message / error handling that every tab reports through. */
export type Workspace = {
  busy: boolean;
  run: (task: () => Promise<void>, onError?: () => Promise<void>) => Promise<void>;
  notify: (message: string) => void;
  fail: (error: string) => void;
  goTo: (tab: WorkspaceTab) => void;
};

export function dateLabel(value: string) {
  return new Date(value).toLocaleString("cs-CZ", { timeZone: "Europe/Prague" });
}

export function Label({ children, title }: { children: ReactNode; title: string }) {
  return (
    <label className="grid gap-1.5 text-sm text-zinc-300">
      {title}
      {children}
    </label>
  );
}

export function Panel({ children, title }: { children: ReactNode; title: string }) {
  return (
    <section className="space-y-5 rounded-2xl border border-white/10 bg-zinc-900/40 p-5 sm:p-7">
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export type Target = { id: string; type: "action" | "opportunity"; title: string };
