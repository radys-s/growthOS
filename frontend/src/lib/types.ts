/**
 * TypeScript mirrors of the backend Pydantic response models (AGENTS.md rule 6).
 * Datetimes arrive as ISO strings in UTC; the UI localizes them.
 */

// backend/app/opportunities/deadlines.py
export type DeadlineKind = "official" | "expected" | "rolling" | "passed" | "unknown";
export type DeadlineInfo = {
  kind: DeadlineKind;
  date: string | null;
  label: string;
  // official deadline found by the deadline watcher: verbatim quote + page it came from
  quote: string | null;
  quote_url: string | null;
};

// backend/app/sources/base.py
export type Eligibility = {
  verified: boolean;
  min_age: number | null;
  max_age: number | null;
  education_levels: string[] | null;
  countries: string[] | null;
  team_size_min: number | null;
  team_size_max: number | null;
  notes: string | null;
};

// backend/app/credentials/__init__.py
export type CredentialType =
  | "industry_certification"
  | "skill_badge"
  | "course_certificate"
  | "participation_badge";
export type Credential = { type: CredentialType; issuer_reputation: number };
export type Tier = "S" | "A" | "B" | "C" | "ignore";
export type CredentialTier = { tier: Tier; score: number };

// backend/app/ranking/engine.py
export type FactorName =
  | "relevance"
  | "gap_coverage"
  | "cv_signal"
  | "skill_gain"
  | "probability"
  | "urgency"
  | "effort"
  | "cost";

export type Candidate = {
  key: string;
  source: "opportunity" | "action";
  origin: string | null; // source adapter of an opportunity: curated | devpost | kaggle
  target_id: string | null;
  kind: string;
  title: string;
  organizer: string | null;
  description: string | null;
  url: string | null;
  signals: string[];
  cv_signal: number | null;
  cv_signal_reason: string | null;
  difficulty: number | null;
  est_hours: number | null;
  cost_eur: number | null;
  deadline: DeadlineInfo | null;
  eligibility: Eligibility | null;
  credential: Credential | null;
  closed: boolean;
  decision: DecisionStatus | null;
  is_new: boolean;
};

export type RankedItem = {
  candidate: Candidate;
  priority: number;
  factors: Record<FactorName, number>;
  contributions: Record<FactorName, number>;
  reasons: string[];
  warnings: string[];
  credential_tier: CredentialTier | null;
};

export type FilteredItem = { candidate: Candidate; reason: string };

export type GapItem = {
  signal: string;
  label: string;
  importance: number;
  coverage: number;
  gap: number;
};

// backend/app/recommendations/service.py
export type Novelty = {
  window_days: number;
  new_items: number;
  new_worthwhile: number;
  already_knew: number;
};

export type Recommendations = {
  goal_id: string;
  goal_title: string;
  generated_at: string;
  top: RankedItem[];
  ranked: RankedItem[];
  filtered: FilteredItem[];
  novelty: Novelty;
};

// backend/app/decisions/schemas.py
export type DecisionStatus = "planned" | "done" | "skipped" | "not_interested" | "already_knew";

// backend/app/goals/schemas.py + app/taxonomy.py
export type FactorWeights = Record<FactorName, number>;
export type RequiredSignal = { signal: string; importance: number };

export type Goal = {
  id: string;
  template_id: string;
  title: string;
  target_date: string | null;
  required_signals: RequiredSignal[];
  weights: FactorWeights;
  active: boolean;
};

export type GoalTemplate = {
  id: string;
  title: string;
  description: string;
  kind: string;
  required_signals: RequiredSignal[];
  weights: FactorWeights;
};

export type Signal = {
  id: string;
  label: string;
  category: "skill" | "evidence" | "credential";
  aliases: string[];
};

// backend/app/profile/schemas.py
export type EducationLevel = "high_school" | "bachelor" | "master" | "phd";
export type ProfileItemKind =
  | "project"
  | "competition"
  | "achievement"
  | "certification"
  | "experience"
  | "publication";

export type ProfileSkill = { signal: string; level: number };

export type ProfileItem = {
  id: string;
  kind: ProfileItemKind;
  title: string;
  description: string | null;
  result: string | null;
  url: string | null;
  signals: string[];
  strength: number;
  achieved_on: string | null;
};

export type Profile = {
  id: string;
  name: string;
  birth_date: string | null;
  country: string;
  education_level: EducationLevel;
  graduation_year: number | null;
  max_cost_eur: number | null;
  weekly_hours_budget: number | null;
  skills: ProfileSkill[];
  items: ProfileItem[];
};
