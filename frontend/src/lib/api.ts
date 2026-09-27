import "server-only";

import type {
  GapItem,
  Goal,
  GoalTemplate,
  Profile,
  Recommendations,
  Signal,
  SourceStatus,
} from "@/lib/types";

export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

/** Mirrors backend `HealthResponse` (backend/app/main.py). */
export type HealthResponse = {
  status: "ok" | "degraded";
  database: "ok" | "unreachable";
  database_dialect: string;
  time: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ");
    }
  } catch {
    // not JSON
  }
  return res.statusText;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status, await detail(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function getHealth(): Promise<HealthResponse | null> {
  try {
    return await api<HealthResponse>("/health", {
      signal: AbortSignal.timeout(3000),
    });
  } catch {
    return null;
  }
}

/** Returns null on 404 (no active goal yet) instead of throwing. */
export async function getRecommendations(goalId?: string): Promise<Recommendations | null> {
  try {
    const query = goalId ? `?goal_id=${encodeURIComponent(goalId)}` : "";
    return await api<Recommendations>(`/recommendations${query}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export const getGoals = () => api<Goal[]>("/goals");
export const getGoalTemplates = () => api<GoalTemplate[]>("/goal-templates");
export const getGaps = (goalId: string) => api<GapItem[]>(`/goals/${goalId}/gaps`);
export const getProfile = () => api<Profile>("/profile");
export const getTaxonomy = () => api<Signal[]>("/taxonomy");
export const getSources = () => api<SourceStatus[]>("/sources");
