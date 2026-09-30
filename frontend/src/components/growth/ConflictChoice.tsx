"use client";

import { growthApi } from "@/lib/growth-api";
import type { PlannedAction } from "@/lib/types";
import { button, dateLabel, type Workspace } from "./ui";

/** Both sides of a calendar conflict with a "keep this one" button each. */
export default function ConflictChoice({
  ws,
  plan,
  onResolved,
  tone = "calendar",
}: {
  ws: Workspace;
  plan: PlannedAction;
  onResolved: () => Promise<void>;
  tone?: "plan" | "calendar";
}) {
  return (
    <>
      {(["local", "remote"] as const).map((side) => {
        const value = plan.conflict?.[side];
        return (
          <div
            key={side}
            className={
              tone === "plan"
                ? "rounded border border-amber-400/20 p-2"
                : "rounded-lg bg-black/20 p-3 text-sm"
            }
          >
            <strong>{side === "local" ? "growthOS" : "Google"}</strong>
            <p>{value?.title ?? "Odstranit časové naplánování"}</p>
            <p>
              {value?.starts_at && dateLabel(value.starts_at)}
              {tone === "calendar" && value?.ends_at && " — " + dateLabel(value.ends_at)}
            </p>
            <p className={`whitespace-pre-wrap ${tone === "calendar" ? "text-zinc-400" : ""}`}>
              {value?.description}
            </p>
            <button
              className={`${button} ${tone === "calendar" ? "mt-2" : ""}`}
              disabled={ws.busy}
              onClick={() =>
                ws.run(async () => {
                  await growthApi(`/calendar/conflicts/${plan.id}`, "POST", {
                    choice: side === "local" ? "local" : "google",
                  });
                  await onResolved();
                })
              }
            >
              Zachovat {side === "local" ? "growthOS" : "Google"}
            </button>
          </div>
        );
      })}
    </>
  );
}
