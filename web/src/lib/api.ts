import type { Options, User, AccountDetail, Crm, Evidence, Mission, Preview, PublicSettings, SourceExcerpt, Summary, ToolRun } from "./types";

// Same-origin: Next.js proxies /api/* to the FastAPI server (see next.config.ts), so the session cookie just works.
export const API = "";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError(0, "Cannot reach the MarketEntryOS server. Is the API running on " + API + "?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export interface RunOptions { replay: boolean; simulate_failure: boolean; use_llm: boolean; caps?: Record<string, number> }

export const api = {
  me: () => req<{ user: User }>("/api/auth/me"),
  settings: () => req<PublicSettings>("/api/settings"),
  options: () => req<Options>("/api/options"),
  preview: (prompt: string, use_llm = true) => req<Preview>("/api/briefs/preview", { method: "POST", body: JSON.stringify({ prompt, use_llm }) }),
  create: (prompt: string, o: RunOptions, overrides?: Record<string, unknown>) =>
    req<{ mission_id: string; status: string }>("/api/missions", { method: "POST", body: JSON.stringify({ prompt, overrides, ...o }) }),
  list: () => req<{ running: { mission_id: string; status: string; prompt: string; created_at: string }[]; missions: Summary[] }>("/api/missions"),
  mission: (id: string) => req<Mission>(`/api/missions/${id}`),
  status: (id: string) => req<{ status: string; state: string | null; error: string | null; prompt?: string | null }>(`/api/missions/${id}/status`),
  account: (id: string, cid: string) => req<AccountDetail>(`/api/missions/${id}/accounts/${cid}`),
  evidence: (id: string, p: { subject?: string; status?: string; q?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams(Object.entries(p).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return req<{ total: number; items: Evidence[] }>(`/api/missions/${id}/evidence?${qs}`);
  },
  source: (id: string, eid: string) => req<SourceExcerpt>(`/api/missions/${id}/evidence/${eid}/source`),
  toolRuns: (id: string) => req<ToolRun[]>(`/api/missions/${id}/tool-runs`),
  crm: (id: string) => req<Crm>(`/api/missions/${id}/crm`),
  setStage: (id: string, rowId: number, stage: string) =>
    req(`/api/missions/${id}/crm/companies/${rowId}`, { method: "PATCH", body: JSON.stringify({ stage }) }),
  patchTask: (id: string, taskId: number, body: { status?: string; draft_text?: string }) =>
    req(`/api/missions/${id}/crm/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(body) }),
  artifactUrl: (id: string, name: string) => `${API}/api/missions/${id}/artifacts/${name}`,
  eventsUrl: (id: string) => `${API}/api/missions/${id}/events`,
};
