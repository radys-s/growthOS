import { decide } from "@/app/actions";
import { SubmitButton } from "@/components/SubmitButton";
import {
  DEADLINE_TONE,
  DECISION_LABELS,
  FACTOR_LABELS,
  FACTOR_ORDER,
  kindLabel,
  ORIGIN_LABELS,
  TIER_TONE,
} from "@/lib/labels";
import type {
  Candidate,
  CredentialTier,
  DecisionStatus,
  RankedItem,
} from "@/lib/types";

const BUTTONS: DecisionStatus[] = [
  "useful",
  "skipped",
  "not_interested",
  "already_knew",
];

export function Badge({
  children,
  tone = "zinc",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  const tones: Record<string, string> = {
    zinc: "border-white/10 bg-white/5 text-zinc-300",
    emerald: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    sky: "border-sky-400/30 bg-sky-400/10 text-sky-300",
    violet: "border-violet-400/30 bg-violet-400/10 text-violet-300",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function TierBadge({ tier }: { tier: CredentialTier | null }) {
  if (!tier || tier.tier === "ignore") return null;
  return (
    <span
      title={`Hodnota certifikátu pro tvůj cíl (skóre ${tier.score.toFixed(2)})`}
    >
      <Badge tone={TIER_TONE[tier.tier]}>Tier {tier.tier}</Badge>
    </span>
  );
}

export function DeadlineQuote({ candidate }: { candidate: Candidate }) {
  const deadline = candidate.deadline;
  if (!deadline?.quote) return null;
  return (
    <p className="text-xs text-zinc-400">
      <span className="text-emerald-300">
        ✓ Termín ověřen citací ze stránky:
      </span>{" "}
      „{deadline.quote}“
      {deadline.quote_url && (
        <>
          {" "}
          <a
            href={deadline.quote_url}
            target="_blank"
            rel="noreferrer"
            className="text-zinc-500 underline hover:text-zinc-300"
          >
            zdroj
          </a>
        </>
      )}
    </p>
  );
}

export function CandidateMeta({
  candidate,
  tier = null,
}: {
  candidate: Candidate;
  tier?: CredentialTier | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400">
      <Badge>{kindLabel(candidate.kind)}</Badge>
      {candidate.origin && candidate.origin !== "curated" && (
        <Badge tone="sky">
          {ORIGIN_LABELS[candidate.origin] ?? candidate.origin}
        </Badge>
      )}
      <TierBadge tier={tier} />
      {candidate.is_new && <Badge tone="emerald">Nové</Badge>}
      {candidate.decision === "planned" && (
        <Badge tone="sky">Naplánováno</Badge>
      )}
      {candidate.decision === "already_knew" && (
        <Badge tone="violet">Už znám</Badge>
      )}
      {candidate.deadline && (
        <span className={DEADLINE_TONE[candidate.deadline.kind]}>
          ⏱ {candidate.deadline.label}
        </span>
      )}
      {candidate.est_hours !== null && <span>~{candidate.est_hours} h</span>}
      {candidate.cost_eur !== null && (
        <span>
          {candidate.cost_eur === 0 ? "zdarma" : `${candidate.cost_eur} €`}
        </span>
      )}
      {candidate.organizer && (
        <span className="truncate">{candidate.organizer}</span>
      )}
    </div>
  );
}

function FactorBars({ item }: { item: RankedItem }) {
  const max = Math.max(
    ...FACTOR_ORDER.map((f) => Math.abs(item.contributions[f])),
    0.0001,
  );
  return (
    <details className="group mt-3 rounded-lg bg-black/20 px-3 py-2 text-xs">
      <summary className="cursor-pointer select-none text-zinc-400 hover:text-zinc-200">
        Proč právě tohle? · skóre {item.priority.toFixed(2)}
      </summary>
      <dl className="mt-3 grid gap-1.5">
        {FACTOR_ORDER.map((factor) => {
          const value = item.contributions[factor];
          const width = `${(Math.abs(value) / max) * 100}%`;
          return (
            <div
              key={factor}
              className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-2"
            >
              <dt className="text-zinc-400">{FACTOR_LABELS[factor]}</dt>
              <dd className="h-1.5 overflow-hidden rounded-full bg-white/5">
                <div
                  className={`h-full rounded-full ${value < 0 ? "bg-rose-400/70" : "bg-emerald-400/70"}`}
                  style={{ width }}
                />
              </dd>
              <dd className="text-right tabular-nums text-zinc-300">
                {value >= 0 ? "+" : ""}
                {value.toFixed(3)}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-2 text-zinc-500">
        Faktory 0–1 × váhy cíle. Zelené přidávají, červené ubírají.
      </p>
    </details>
  );
}

function DecisionButtons({ candidate }: { candidate: Candidate }) {
  if (!candidate.target_id) return null;
  return (
    <form action={decide} className="mt-3 flex flex-wrap gap-1.5">
      <input type="hidden" name="target_type" value={candidate.source} />
      <input type="hidden" name="target_id" value={candidate.target_id} />
      <a
        className="rounded-md border border-emerald-400/30 px-2.5 py-1 text-xs text-emerald-200"
        href={`/growth?tab=plan&target=${candidate.target_id}&type=${candidate.source}&title=${encodeURIComponent(candidate.title)}`}
      >
        Naplánovat
      </a>
      <a
        className="rounded-md border border-emerald-400/30 px-2.5 py-1 text-xs text-emerald-200"
        href={`/growth?tab=complete&target=${candidate.target_id}&type=${candidate.source}&title=${encodeURIComponent(candidate.title)}`}
      >
        Zapsat výsledek
      </a>
      {BUTTONS.filter((status) => status !== candidate.decision).map(
        (status) => (
          <SubmitButton
            key={status}
            name="status"
            value={status}
            className={`rounded-md border px-2.5 py-1 text-xs transition ${
              status === "planned" || status === "done"
                ? "border-emerald-400/30 text-emerald-200 hover:bg-emerald-400/10"
                : "border-white/10 text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
            }`}
          >
            {DECISION_LABELS[status]}
          </SubmitButton>
        ),
      )}
    </form>
  );
}

export function RecommendationCard({
  item,
  rank,
}: {
  item: RankedItem;
  rank: number;
}) {
  const { candidate } = item;
  return (
    <article className="rounded-xl border border-white/10 bg-zinc-950/40 p-4">
      <div className="flex gap-3">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-400/15 text-sm font-semibold text-emerald-300">
          {rank}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="font-medium text-zinc-50">
            {candidate.url ? (
              <a
                href={candidate.url}
                target="_blank"
                rel="noreferrer"
                className="hover:text-emerald-300 hover:underline"
              >
                {candidate.title}
              </a>
            ) : (
              candidate.title
            )}
          </h3>
          <div className="mt-1 flex flex-col gap-1">
            <CandidateMeta candidate={candidate} tier={item.credential_tier} />
            <DeadlineQuote candidate={candidate} />
          </div>
          {item.reasons.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm text-zinc-200">
              {item.reasons.map((reason) => (
                <li key={reason} className="flex gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          )}
          {item.warnings.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-amber-300/90">
              {item.warnings.map((warning) => (
                <li key={warning}>⚠ {warning}</li>
              ))}
            </ul>
          )}
          <FactorBars item={item} />
          <DecisionButtons candidate={candidate} />
        </div>
      </div>
    </article>
  );
}
