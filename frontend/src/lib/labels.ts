import type { DecisionStatus, DeadlineKind, FactorName, ProfileItemKind, Tier } from "@/lib/types";

export const KIND_LABELS: Record<string, string> = {
  competition: "Soutěž",
  olympiad: "Olympiáda",
  hackathon: "Hackathon",
  internship: "Stáž",
  scholarship: "Stipendium",
  program: "Program",
  summer_school: "Letní škola",
  certification: "Certifikace",
  build: "Postav",
  learn: "Nauč se",
  certify: "Certifikuj se",
  publish: "Zveřejni",
  apply: "Přihlas se",
};

export const kindLabel = (kind: string) => KIND_LABELS[kind] ?? kind;

export const FACTOR_LABELS: Record<FactorName, string> = {
  relevance: "Relevance k cíli",
  gap_coverage: "Pokrytí mezer",
  cv_signal: "Signál do CV",
  skill_gain: "Nové dovednosti",
  probability: "Šance na úspěch",
  urgency: "Naléhavost",
  effort: "Časová náročnost",
  cost: "Cena",
};

export const FACTOR_ORDER: FactorName[] = [
  "gap_coverage",
  "relevance",
  "cv_signal",
  "skill_gain",
  "probability",
  "urgency",
  "effort",
  "cost",
];

export const DECISION_LABELS: Record<DecisionStatus, string> = {
  useful: "Užitečné",
  reversed: "Vráceno zpět",
  planned: "Naplánovat",
  done: "Hotovo",
  skipped: "Přeskočit",
  not_interested: "Nezajímá mě",
  already_knew: "Už znám",
};

export const DEADLINE_TONE: Record<DeadlineKind, string> = {
  official: "text-emerald-300",
  expected: "text-amber-300",
  rolling: "text-sky-300",
  passed: "text-zinc-500",
  unknown: "text-zinc-400",
};

export const ITEM_KIND_LABELS: Record<ProfileItemKind, string> = {
  project: "Projekt",
  competition: "Soutěž",
  achievement: "Úspěch",
  certification: "Certifikát",
  experience: "Praxe",
  publication: "Publikace",
};

export const LEVEL_LABELS = ["—", "Základy", "Pokročilý", "Silný", "Expert"];

export const EDUCATION_LABELS: Record<string, string> = {
  high_school: "Střední škola",
  bachelor: "Bakalář",
  master: "Magistr",
  phd: "Doktorand",
};

export const ORIGIN_LABELS: Record<string, string> = {
  curated: "Kurátorské",
  devpost: "Devpost",
  kaggle: "Kaggle",
};

export const TIER_TONE: Record<Tier, string> = {
  S: "emerald",
  A: "sky",
  B: "violet",
  C: "zinc",
  ignore: "zinc",
};

/** What to put in backend/.env to switch a source on. */
export const SOURCE_SETUP_HINT: Record<string, string> = {
  kaggle: "Doplň KAGGLE_USERNAME a KAGGLE_KEY do backend/.env (kaggle.com → Settings → API).",
  deadline_watch: "Doplň LLM_BASE_URL (OmniRoute) a LLM_API_KEY do backend/.env a spusť OmniRoute.",
};

const PRAGUE_TIME = new Intl.DateTimeFormat("cs-CZ", {
  timeZone: "Europe/Prague",
  day: "numeric",
  month: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
export const formatPrague = (iso: string) => PRAGUE_TIME.format(new Date(iso));
