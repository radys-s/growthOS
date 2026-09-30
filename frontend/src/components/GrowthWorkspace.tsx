"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { growthApi } from "@/lib/growth-api";
import { DECISION_LABELS } from "@/lib/labels";
import type {
  CalendarConnect,
  CalendarStatus,
  CalendarSync,
  DecisionEvent,
  DecisionStatus,
  ImportProposal,
  ItemInput,
  PlannedAction,
  PlanInput,
  ProfileItem,
  ProgressSnapshot,
  Signal,
  Week,
} from "@/lib/types";

const field =
  "w-full rounded-lg border border-white/15 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-400 focus:outline-none";
const button =
  "rounded-lg border border-emerald-400/30 px-4 py-2 text-sm text-emerald-200 transition-colors hover:bg-emerald-400/10 disabled:opacity-50";
const emptyItem: ItemInput = {
  kind: "project",
  title: "",
  description: "",
  result: "",
  url: null,
  signals: [],
  strength: 1,
  achieved_on: null,
};
function dateLabel(value: string) {
  return new Date(value).toLocaleString("cs-CZ", { timeZone: "Europe/Prague" });
}
function Label({ children, title }: { children: ReactNode; title: string }) {
  return (
    <label className="grid gap-1.5 text-sm text-zinc-300">
      {title}
      {children}
    </label>
  );
}
function Panel({ children, title }: { children: ReactNode; title: string }) {
  return (
    <section className="space-y-5 rounded-2xl border border-white/10 bg-zinc-900/40 p-5 sm:p-7">
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function EvidenceForm({
  initial,
  source,
  completion,
  onSave,
}: {
  initial: ItemInput;
  source?: ImportProposal;
  completion?: boolean;
  onSave: (item: ItemInput, kind: "claimed" | "demonstrated") => Promise<void>;
}) {
  const [item, setItem] = useState(initial);
  const [kind, setKind] = useState<"claimed" | "demonstrated">(
    completion ? "demonstrated" : "claimed",
  );
  const [signals, setSignals] = useState<Signal[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    growthApi<Signal[]>("/taxonomy")
      .then(setSignals)
      .catch(() => setError("Nelze načíst dovednosti. Zkus stránku obnovit."));
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(item, kind);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Uložení selhalo.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      {source && (
        <details className="rounded-lg bg-black/20 p-3 text-sm">
          <summary className="cursor-pointer text-emerald-300">
            Původní zdroj: {source.reference}
          </summary>
          <pre className="mt-3 max-h-60 overflow-auto whitespace-pre-wrap font-sans text-zinc-400">
            {source.excerpt}
          </pre>
        </details>
      )}
      <Label title="Název">
        <input
          required
          maxLength={300}
          className={field}
          value={item.title}
          onChange={(e) => setItem({ ...item, title: e.target.value })}
        />
      </Label>
      <Label title="Popis">
        <textarea
          className={field}
          rows={3}
          value={item.description ?? ""}
          onChange={(e) => setItem({ ...item, description: e.target.value })}
        />
      </Label>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label title="Druh výsledku">
          <select
            className={field}
            value={item.kind}
            onChange={(e) =>
              setItem({ ...item, kind: e.target.value as ItemInput["kind"] })
            }
          >
            <option value="project">Projekt</option>
            <option value="competition">Soutěž</option>
            <option value="achievement">Úspěch</option>
            <option value="certification">Certifikace</option>
            <option value="experience">Zkušenost</option>
            <option value="publication">Publikace</option>
          </select>
        </Label>
        <Label title="Co tento záznam představuje">
          <select
            className={field}
            disabled={completion}
            value={kind}
            onChange={(e) => setKind(e.target.value as typeof kind)}
          >
            <option value="claimed">Tvrzení / zájem (nemění pokrytí)</option>
            <option value="demonstrated">Konkrétní doložený výsledek</option>
          </select>
        </Label>
      </div>
      <p className="text-xs text-zinc-400">
        README ani seznam knihoven nedokazují zvládnutí technologie. Doložený
        výsledek potvrď jen podle toho, co jsi skutečně dokončil.
      </p>
      <Label title="Konkrétní výsledek">
        <input
          className={field}
          maxLength={200}
          required={kind === "demonstrated"}
          value={item.result ?? ""}
          onChange={(e) => setItem({ ...item, result: e.target.value })}
          placeholder="Co vzniklo, jak jsi ověřil funkčnost, jaký byl výsledek?"
        />
      </Label>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label title="Datum výsledku">
          <input
            type="date"
            required={completion}
            className={field}
            value={item.achieved_on ?? ""}
            onChange={(e) =>
              setItem({ ...item, achieved_on: e.target.value || null })
            }
          />
        </Label>
        <Label title="Síla důkazu (0–4)">
          <select
            className={field}
            value={item.strength}
            onChange={(e) =>
              setItem({ ...item, strength: Number(e.target.value) })
            }
          >
            <option value={0}>0 · Bez prokázaného výsledku</option>
            <option value={1}>1 · První praktický výsledek</option>
            <option value={2}>2 · Samostatně dokončeno</option>
            <option value={3}>3 · Silný ověřený výsledek</option>
            <option value={4}>4 · Výjimečný, opakovaně doložený</option>
          </select>
        </Label>
      </div>
      <p className="text-xs text-zinc-400">
        Pokrytí cíle se zvýší jen tehdy, když je tento potvrzený důkaz silnější
        než už zaznamenaná dovednost nebo výsledek pro stejný signál.
      </p>
      <Label title="Odkaz na důkaz (volitelné)">
        <input
          type="url"
          className={field}
          value={item.url ?? ""}
          onChange={(e) => setItem({ ...item, url: e.target.value || null })}
        />
      </Label>
      <fieldset className="rounded-lg border border-white/10 p-3">
        <legend className="px-1 text-sm">Co výsledek dokládá</legend>
        <div className="grid max-h-48 gap-2 overflow-auto sm:grid-cols-2">
          {signals.map((signal) => (
            <label
              key={signal.id}
              className="flex items-center gap-2 text-xs text-zinc-300"
            >
              <input
                type="checkbox"
                checked={item.signals.includes(signal.id)}
                onChange={(e) =>
                  setItem({
                    ...item,
                    signals: e.target.checked
                      ? [...item.signals, signal.id]
                      : item.signals.filter((s) => s !== signal.id),
                  })
                }
              />
              {signal.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="flex gap-2 text-sm">
        <input required type="checkbox" />
        Potvrzuji správnost údajů a chci je přidat do profilu.
      </label>
      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      <button className={button} disabled={busy || !signals.length}>
        {busy ? "Ukládám…" : "Potvrdit a přidat do profilu"}
      </button>
    </form>
  );
}

function localInput(iso: string | null) {
  if (!iso) return "";
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Prague",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
  return parts.replace(" ", "T");
}
function pragueTime(value: string, choice: string): string | null {
  if (!value) return null;
  const candidates = ["+02:00", "+01:00"]
    .map((offset) => value + ":00" + offset)
    .filter((iso) => localInput(iso) === value);
  if (!candidates.length)
    throw new Error("Tento čas v Praze neexistuje kvůli změně na letní čas.");
  if (candidates.length === 2 && !choice)
    throw new Error("Tento čas nastává dvakrát. Vyber letní nebo zimní čas.");
  return new Date(
    candidates.find((iso) => iso.endsWith(choice)) ?? candidates[0],
  ).toISOString();
}

function PlanForm({
  initial,
  target,
  onSave,
}: {
  initial?: PlannedAction;
  target: { id: string; type: "action" | "opportunity"; title: string };
  onSave: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const data: PlanInput = {
        title: String(f.get("title")),
        description: String(f.get("description")),
        est_hours: Number(f.get("hours")),
        week_of: String(f.get("week")),
        status: String(f.get("status")) as PlanInput["status"],
        target_id: initial?.target_id ?? (target.id || null),
        target_type: initial?.target_type ?? (target.id ? target.type : null),
        starts_at: pragueTime(String(f.get("start")), String(f.get("offset"))),
        ends_at: pragueTime(String(f.get("end")), String(f.get("offset"))),
      };
      await growthApi(
        initial ? `/plans/${initial.id}` : "/plans",
        initial ? "PUT" : "POST",
        data,
      );
      await onSave();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Uložení selhalo.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <Label title="Akce">
        <input
          className={field}
          name="title"
          required
          maxLength={300}
          defaultValue={initial?.title ?? target.title}
        />
      </Label>
      <Label title="Poznámka">
        <textarea
          className={field}
          name="description"
          defaultValue={initial?.description ?? ""}
        />
      </Label>
      <div className="grid gap-4 sm:grid-cols-3">
        <Label title="Odhad práce (hodiny)">
          <input
            className={field}
            name="hours"
            type="number"
            min="0.25"
            max="168"
            step="0.25"
            defaultValue={initial?.est_hours ?? 2}
            required
          />
        </Label>
        <Label title="Den v plánovaném týdnu">
          <input
            className={field}
            type="date"
            name="week"
            defaultValue={
              initial?.week_of ?? new Date().toLocaleDateString("en-CA")
            }
            required
          />
        </Label>
        <Label title="Stav">
          <select
            className={field}
            name="status"
            defaultValue={initial?.status ?? "planned"}
          >
            <option value="planned">Naplánováno</option>
            <option value="in_progress">Rozpracováno</option>
            <option value="done">Dokončeno (bez přidání důkazu)</option>
            <option value="cancelled">Zrušeno</option>
          </select>
        </Label>
      </div>
      <p className="text-sm text-zinc-400">
        Čas je volitelný, v pásmu Praha. Vyplněním vytváříš vlastní pracovní
        blok; odhadované deadliny se nepřenášejí.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label title="Začátek">
          <input
            className={field}
            type="datetime-local"
            name="start"
            defaultValue={localInput(initial?.starts_at ?? null)}
          />
        </Label>
        <Label title="Konec">
          <input
            className={field}
            type="datetime-local"
            name="end"
            defaultValue={localInput(initial?.ends_at ?? null)}
          />
        </Label>
      </div>
      <Label title="Při podzimní změně času">
        <select className={field} name="offset" defaultValue="">
          <option value="">Automaticky, pokud je čas jednoznačný</option>
          <option value="+02:00">První výskyt · letní čas</option>
          <option value="+01:00">Druhý výskyt · zimní čas</option>
        </select>
      </Label>
      {error && (
        <p role="alert" className="text-rose-300">
          {error}
        </p>
      )}
      <button disabled={busy} className={button}>
        {busy ? "Ukládám…" : "Uložit plán"}
      </button>
    </form>
  );
}

export default function GrowthWorkspace({
  initialTab,
  target,
}: {
  initialTab: string;
  target: { id: string; type: "action" | "opportunity"; title: string };
}) {
  const [tab, setTab] = useState(initialTab);
  const [proposals, setProposals] = useState<ImportProposal[]>([]),
    [active, setActive] = useState<ImportProposal | null>(null);
  const [week, setWeek] = useState<Week | null>(null),
    [weekDate, setWeekDate] = useState("");
  const [events, setEvents] = useState<DecisionEvent[]>([]),
    [progress, setProgress] = useState<ProgressSnapshot[]>([]);
  const [conflicts, setConflicts] = useState<PlannedAction[]>([]);
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null),
    [editing, setEditing] = useState<PlannedAction | null>(null);
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  async function loadWeek(day = weekDate) {
    setWeek(await growthApi<Week>("/plans" + (day ? `?week_of=${day}` : "")));
  }
  async function loadCalendar() {
    setCalendar(await growthApi<CalendarStatus>("/calendar/status"));
    setConflicts(await growthApi<PlannedAction[]>("/calendar/conflicts"));
  }
  async function run(task: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend neodpovídá.");
      await loadCalendar().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    Promise.all([
      growthApi<PlannedAction[]>("/calendar/conflicts").then(setConflicts),
      growthApi<Week>("/plans").then(setWeek),
      growthApi<CalendarStatus>("/calendar/status").then(setCalendar),
      growthApi<DecisionEvent[]>("/history").then(setEvents),
      growthApi<ProgressSnapshot[]>("/progress").then(setProgress),
    ]).catch(() =>
      setError("Backend neodpovídá. Spusť growthOS a obnov stránku."),
    );
  }, []);
  async function preview(
    event: FormEvent<HTMLFormElement>,
    kind: "text" | "file" | "github",
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      const body =
        kind === "file"
          ? form
          : kind === "text"
            ? { text: form.get("text") }
            : { repository: form.get("repository") };
      const rows = await growthApi<ImportProposal[]>(
        `/imports/${kind}`,
        "POST",
        body,
      );
      setProposals(rows);
      setActive(null);
      setMessage(
        `${rows.length} návrhů k posouzení. Profil se zatím nezměnil.`,
      );
    });
  }
  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8 sm:px-8">
      <header>
        <p className="text-xs uppercase tracking-widest text-emerald-300">
          growthOS / pracovní prostor
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Od plánu k doloženému výsledku
        </h1>
        <p className="mt-3 text-zinc-400">
          Importuj podklady, vyber práci na tento týden a sleduj, co se opravdu
          změnilo.
        </p>
      </header>
      <div
        className="flex flex-wrap gap-2"
        aria-label="Sekce pracovního prostoru"
      >
        {[
          ["imports", "Importy"],
          ["plan", "Týdenní plán"],
          ["history", "Historie a progres"],
          ["calendar", "Google kalendář"],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => {
              setTab(id);
              setError("");
              setMessage("");
            }}
            aria-pressed={tab === id}
            className={`${button} ${tab === id ? "bg-emerald-400/15" : ""}`}
          >
            {label}
          </button>
        ))}
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/30 p-4 text-rose-300"
        >
          {error}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="rounded-xl border border-emerald-400/30 p-4 text-emerald-200"
        >
          {message}
        </p>
      )}
      {tab === "imports" && (
        <>
          <Panel title="Podklady zůstávají lokálně">
            <p className="text-sm text-zinc-400">
              CV ani obsah repozitáře neposíláme AI. Návrhy můžeš upravit a
              potvrdit jednotlivě; původní profil zůstane zachován.
            </p>
            <form onSubmit={(e) => preview(e, "text")} className="space-y-3">
              <Label title="Text CV">
                <textarea
                  name="text"
                  className={field}
                  rows={5}
                  maxLength={100000}
                  required
                />
              </Label>
              <button disabled={busy} className={button}>
                Připravit návrhy z textu
              </button>
            </form>
            <div className="grid gap-6 border-t border-white/10 pt-5 sm:grid-cols-2">
              <form onSubmit={(e) => preview(e, "file")} className="space-y-3">
                <Label title="PDF nebo DOCX (nejvýše 5 MB)">
                  <input
                    className={field}
                    name="file"
                    type="file"
                    accept=".pdf,.docx"
                    required
                  />
                </Label>
                <p className="text-xs text-zinc-400">
                  Pro naskenované PDF vlož text ručně.
                </p>
                <button className={button} disabled={busy}>
                  Načíst soubor
                </button>
              </form>
              <form
                onSubmit={(e) => preview(e, "github")}
                className="space-y-3"
              >
                <Label title="Veřejný GitHub repozitář">
                  <input
                    className={field}
                    name="repository"
                    placeholder="vlastník/repozitář"
                    required
                  />
                </Label>
                <p className="text-xs text-zinc-400">
                  Čteme metadata, README a závislosti. Kód nespouštíme.
                </p>
                <button className={button} disabled={busy}>
                  Analyzovat repozitář
                </button>
              </form>
            </div>
          </Panel>
          {proposals.length > 0 && (
            <Panel title="Návrhy k potvrzení">
              <div className="grid gap-2">
                {proposals.map((p) => (
                  <button
                    className="rounded-lg border border-white/10 p-3 text-left hover:bg-white/5 disabled:opacity-50"
                    key={p.id}
                    disabled={!!p.confirmed_item_id}
                    onClick={() => setActive(p)}
                  >
                    {p.proposed.title}
                    <span className="ml-2 text-xs text-zinc-400">
                      {p.confirmed_item_id ? "Potvrzeno" : "Posoudit →"}
                    </span>
                  </button>
                ))}
              </div>
            </Panel>
          )}
          {active && (
            <Panel title="Posoudit návrh">
              <EvidenceForm
                key={active.id}
                initial={active.proposed}
                source={active}
                onSave={async (item, kind) => {
                  const saved = await growthApi<ProfileItem>(
                    `/imports/${active.id}/confirm`,
                    "POST",
                    { item, evidence_kind: kind, confirmed: true },
                  );
                  setProposals((rows) =>
                    rows.map((p) =>
                      p.id === active.id
                        ? { ...p, confirmed_item_id: saved.id }
                        : p,
                    ),
                  );
                  setActive(null);
                  setMessage(
                    "Potvrzeno. Existující záznamy zůstaly zachovány.",
                  );
                  setProgress(await growthApi<ProgressSnapshot[]>("/progress"));
                }}
              />
            </Panel>
          )}
        </>
      )}
      {tab === "complete" && (
        <Panel title="Zapsat dokončený výsledek">
          {target.id ? (
            <EvidenceForm
              initial={{ ...emptyItem, title: target.title }}
              completion
              onSave={async (item) => {
                await growthApi("/completions", "POST", {
                  target_type: target.type,
                  target_id: target.id,
                  item,
                  evidence_kind: "demonstrated",
                  confirmed: true,
                });
                setMessage(
                  "Výsledek je potvrzený. Profil, mezery a doporučení se přepočítaly.",
                );
                setTab("history");
                setEvents(await growthApi<DecisionEvent[]>("/history"));
                setProgress(await growthApi<ProgressSnapshot[]>("/progress"));
              }}
            />
          ) : (
            <p>Vyber akci na dashboardu a otevři „Zapsat výsledek“.</p>
          )}
        </Panel>
      )}
      {tab === "plan" && (
        <>
          <Panel title="Tento týden">
            <Label title="Zobrazit týden obsahující datum">
              <input
                className={field}
                type="date"
                value={weekDate}
                onChange={(e) => {
                  setWeekDate(e.target.value);
                  void run(() => loadWeek(e.target.value));
                }}
              />
            </Label>
            {week && (
              <>
                <p
                  className={
                    week.over_budget ? "text-amber-300" : "text-emerald-300"
                  }
                >
                  {week.planned_hours} h naplánováno /{" "}
                  {week.budget_hours ?? "nenastavený"} h rozpočet{" "}
                  {week.over_budget && "· Plán přesahuje tvou kapacitu"}
                </p>
                {!week.plans.length && (
                  <p className="text-zinc-400">
                    Tento týden zatím nemá plán. Začni jednou konkrétní akcí.
                  </p>
                )}
                <div className="space-y-3">
                  {week.plans.map((p) => (
                    <article
                      key={p.id}
                      className="rounded-xl border border-white/10 p-4"
                    >
                      <div className="flex flex-wrap justify-between gap-2">
                        <h3 className="font-medium">{p.title}</h3>
                        <span className="text-sm text-zinc-400">
                          {p.est_hours} h ·{" "}
                          {
                            {
                              planned: "naplánováno",
                              in_progress: "rozpracováno",
                              done: "dokončeno",
                              cancelled: "zrušeno",
                            }[p.status]
                          }
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-zinc-400">
                        {p.starts_at
                          ? dateLabel(p.starts_at) +
                            " — " +
                            dateLabel(p.ends_at!)
                          : "Bez pevného času"}
                      </p>
                      <p className="mt-2 whitespace-pre-wrap text-sm">
                        {p.description}
                      </p>
                      {p.conflict ? (
                        <div className="mt-3 space-y-2 text-sm text-amber-300">
                          <p>Změny na obou stranách. Vyber, kterou zachovat:</p>
                          {(["local", "remote"] as const).map((side) => (
                            <div
                              key={side}
                              className="rounded border border-amber-400/20 p-2"
                            >
                              <strong>
                                {side === "local" ? "growthOS" : "Google"}
                              </strong>
                              <p>
                                {p.conflict?.[side]?.title ??
                                  "Odstranit časové naplánování"}
                              </p>
                              <p>
                                {p.conflict?.[side]?.starts_at &&
                                  dateLabel(p.conflict[side]!.starts_at)}
                              </p>
                              <p className="whitespace-pre-wrap">
                                {p.conflict?.[side]?.description}
                              </p>
                              <button
                                className={button}
                                disabled={busy}
                                onClick={() =>
                                  run(async () => {
                                    await growthApi(
                                      `/calendar/conflicts/${p.id}`,
                                      "POST",
                                      {
                                        choice:
                                          side === "local" ? "local" : "google",
                                      },
                                    );
                                    await loadWeek();
                                  })
                                }
                              >
                                Zachovat{" "}
                                {side === "local" ? "growthOS" : "Google"}
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <button
                          className={`${button} mt-3`}
                          onClick={() => setEditing(p)}
                        >
                          Upravit
                        </button>
                      )}
                      {p.target_id && p.status !== "done" && (
                        <a
                          className="ml-3 text-sm text-emerald-300 underline"
                          href={`/growth?tab=complete&target=${p.target_id}&type=${p.target_type}&title=${encodeURIComponent(p.title)}`}
                        >
                          Zapsat výsledek
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              </>
            )}
          </Panel>
          <Panel title={editing ? "Upravit plán" : "Přidat pracovní blok"}>
            <PlanForm
              key={editing?.id ?? target.id}
              initial={editing ?? undefined}
              target={target}
              onSave={async () => {
                setEditing(null);
                await loadWeek();
                setMessage(
                  "Plán uložen. Pro přenos do Google spusť synchronizaci.",
                );
              }}
            />
            {editing && (
              <button className={button} onClick={() => setEditing(null)}>
                Zrušit úpravu
              </button>
            )}
          </Panel>
        </>
      )}
      {tab === "history" && (
        <>
          <Panel title="Změny pokrytí cílů">
            <p className="text-sm text-zinc-400">
              Záznam před a po potvrzení. Vyšší pokrytí samo o sobě nedokazuje
              lepší kvalitu doporučení.
            </p>
            {!progress.length && <p>Zatím nejsou potvrzené nové výsledky.</p>}
            <ol className="space-y-4">
              {progress.map((p) => (
                <li
                  key={p.id}
                  className="border-l-2 border-emerald-400/30 pl-4"
                >
                  <p>{p.reason}</p>
                  <p className="text-xs text-zinc-500">
                    {dateLabel(p.created_at)} · cíl {p.goal_id.slice(0, 8)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-300">
                    {Object.entries(p.coverage)
                      .map(
                        ([key, value]) =>
                          `${key}: ${Math.round(value * 100)} %`,
                      )
                      .join(" · ")}
                  </p>
                </li>
              ))}
            </ol>
          </Panel>
          <Panel title="Historie rozhodnutí">
            <p className="text-sm text-zinc-400">
              Vrácení rozhodnutí přidá nový záznam. Dřívější výsledky ani důkazy
              nemaže.
            </p>
            {!events.length && <p>Zatím žádná rozhodnutí.</p>}
            <ol className="space-y-3">
              {events.map((event) => (
                <li
                  key={event.id}
                  className="flex flex-wrap justify-between gap-2 border-b border-white/10 pb-3"
                >
                  <div>
                    <p>
                      {DECISION_LABELS[event.status as DecisionStatus] ??
                        event.status}{" "}
                      · {event.note ?? event.target_id.slice(0, 8)}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {dateLabel(event.created_at)}
                    </p>
                  </div>
                  {event.status !== "reversed" && (
                    <button
                      className={button}
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await growthApi(
                            `/decisions/${event.target_type}/${event.target_id}`,
                            "DELETE",
                          );
                          setEvents(
                            await growthApi<DecisionEvent[]>("/history"),
                          );
                          setMessage(
                            "Rozhodnutí vráceno; historie a důkazy zůstaly zachovány.",
                          );
                        })
                      }
                    >
                      Vrátit rozhodnutí
                    </button>
                  )}
                </li>
              ))}
            </ol>
          </Panel>
        </>
      )}
      {tab === "calendar" && (
        <Panel title="Vyhrazený kalendář growthOS">
          <p className="text-sm text-zinc-400">
            Přenáší pouze naplánované pracovní bloky do kalendáře vytvořeného
            pro growthOS. Osobní kalendáře nečte. Změny se přenesou po spuštění
            synchronizace.
          </p>
          <p>
            Stav:{" "}
            <strong>
              {(
                {
                  connected: "připojeno",
                  disconnected: "nepřipojeno",
                  needs_calendar: "vytvoř kalendář",
                  creation_pending: "vytvoření čeká na ověření",
                  reauthorize: "obnov přihlášení",
                  calendar_missing: "kalendář chybí",
                } as Record<string, string>
              )[calendar?.state ?? ""] ?? "načítání"}
            </strong>
          </p>
          {calendar && !calendar.configured && (
            <p className="rounded-lg border border-amber-400/30 p-4 text-sm text-amber-200">
              Připojení zatím není nastavené. Doplň OAuth údaje podle README.
              Živé propojení bude možné ověřit až po přihlášení.
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <button
              className={button}
              disabled={busy || !calendar?.configured}
              onClick={() =>
                run(async () => {
                  const result = await growthApi<CalendarConnect>(
                    "/calendar/connect",
                    "POST",
                  );
                  window.location.assign(result.authorization_url);
                })
              }
            >
              Připojit / obnovit Google
            </button>
            <button
              className={button}
              disabled={busy || calendar?.state !== "needs_calendar"}
              onClick={() =>
                run(async () => {
                  await growthApi("/calendar/create", "POST");
                  await loadCalendar();
                })
              }
            >
              Vytvořit growthOS kalendář
            </button>
            <button
              className={button}
              disabled={busy || !calendar?.has_calendar}
              onClick={() =>
                run(async () => {
                  const result = await growthApi<CalendarSync>(
                    "/calendar/sync",
                    "POST",
                  );
                  await loadWeek();
                  await loadCalendar();
                  setMessage(
                    `Synchronizováno ${result.changed} změn; konflikty: ${result.conflicts}. Konflikty vyřešíš níže.` +
                      (result.skipped.length
                        ? ` Přeskočeno: ${result.skipped.join(" ")}`
                        : ""),
                  );
                })
              }
            >
              Synchronizovat změny
            </button>
            <button
              className={button}
              disabled={busy || calendar?.state === "disconnected"}
              onClick={() =>
                run(async () => {
                  await growthApi("/calendar/disconnect", "POST");
                  await loadCalendar();
                  setMessage(
                    "Lokální přihlašovací údaje odstraněny. Události zůstávají v Google.",
                  );
                })
              }
            >
              Odpojit
            </button>
          </div>
          {calendar?.state === "creation_pending" && (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                void run(async () => {
                  await growthApi("/calendar/recover", "POST", {
                    calendar_id: form.get("calendar_id"),
                  });
                  await loadCalendar();
                });
              }}
            >
              <p className="text-sm text-amber-300">
                Po výpadku mohl kalendář vzniknout. V nastavení Google kalendáře
                growthOS zkopíruj jeho ID. Ověříme označení tohoto připojení,
                osobní kalendář nepřipojíme.
              </p>
              <Label title="ID vytvořeného growthOS kalendáře">
                <input className={field} name="calendar_id" required />
              </Label>
              <button className={button} disabled={busy}>
                Ověřit a obnovit připojení
              </button>
            </form>
          )}
          {calendar?.state === "calendar_missing" && (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void run(async () => {
                  await growthApi("/calendar/replace-missing", "POST", {
                    confirmed: true,
                  });
                  await loadCalendar();
                });
              }}
            >
              <p className="text-sm text-amber-300">
                Nejdřív zkus původní Google účet. Pokud byl kalendář skutečně
                smazán, můžeš připravit nový; plán a důkazy zůstanou zachované.
              </p>
              <label className="flex gap-2 text-sm">
                <input type="checkbox" required />
                Potvrzuji, že původní kalendář byl odstraněn a chci vytvořit
                náhradní.
              </label>
              <button className={button} disabled={busy}>
                Připravit náhradní kalendář
              </button>
            </form>
          )}
          {conflicts.map((p) => (
            <div
              key={p.id}
              className="space-y-3 rounded-xl border border-amber-400/30 p-4"
            >
              <h3 className="font-medium text-amber-300">
                Konflikt: {p.title}
              </h3>
              {(["local", "remote"] as const).map((side) => (
                <div key={side} className="rounded-lg bg-black/20 p-3 text-sm">
                  <strong>{side === "local" ? "growthOS" : "Google"}</strong>
                  <p>
                    {p.conflict?.[side]?.title ??
                      "Odstranit časové naplánování"}
                  </p>
                  <p>
                    {p.conflict?.[side]?.starts_at &&
                      dateLabel(p.conflict[side]!.starts_at)}{" "}
                    {p.conflict?.[side]?.ends_at &&
                      " — " + dateLabel(p.conflict[side]!.ends_at)}
                  </p>
                  <p className="whitespace-pre-wrap text-zinc-400">
                    {p.conflict?.[side]?.description}
                  </p>
                  <button
                    disabled={busy}
                    className={`${button} mt-2`}
                    onClick={() =>
                      run(async () => {
                        await growthApi(`/calendar/conflicts/${p.id}`, "POST", {
                          choice: side === "local" ? "local" : "google",
                        });
                        await loadCalendar();
                        await loadWeek();
                      })
                    }
                  >
                    Zachovat {side === "local" ? "growthOS" : "Google"}
                  </button>
                </div>
              ))}
            </div>
          ))}
        </Panel>
      )}
    </main>
  );
}
