import { connection } from "next/server";

import { getHealth } from "@/lib/api";

export async function HealthBadge() {
  await connection();
  const health = await getHealth();

  const label = !health
    ? "API offline"
    : health.status === "ok"
      ? `API ok · ${health.database_dialect}`
      : "API degraded · DB unreachable";
  const tone = !health
    ? "bg-red-500"
    : health.status === "ok"
      ? "bg-emerald-500"
      : "bg-amber-500";

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-zinc-300">
      <span className={`h-2 w-2 rounded-full ${tone}`} aria-hidden />
      {label}
    </span>
  );
}
