const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export async function growthApi<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const file = body instanceof FormData;
  const response = await fetch(BASE + path, {
    method,
    cache: "no-store",
    signal: AbortSignal.timeout(120000),
    headers: file ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : file ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((d: { msg: string }) => d.msg).join("; ")
          : "Požadavek se nezdařil.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
