const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function readApiError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown; error?: string };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail && typeof body.detail === "object") {
      const detail = body.detail as { message?: string; error?: string };
      return detail.message ?? detail.error ?? `API request failed (${response.status})`;
    }
    return body.error ?? `API request failed (${response.status})`;
  } catch {
    return `API request failed (${response.status})`;
  }
}

export async function requestApiJson<T>(endpoint: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!response.ok) throw new Error(await readApiError(response));
    return await response.json() as T;
  } finally {
    window.clearTimeout(timeout);
  }
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
