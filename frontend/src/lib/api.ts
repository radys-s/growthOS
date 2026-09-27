export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

/** Mirrors backend `HealthResponse` (backend/app/main.py). */
export type HealthResponse = {
  status: "ok" | "degraded";
  database: "ok" | "unreachable";
  database_dialect: string;
  time: string;
};

export async function getHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return null;
    return (await res.json()) as HealthResponse;
  } catch {
    return null;
  }
}
