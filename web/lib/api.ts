import { ActivityEntry, HubRequest, Plan } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function listRequests(params?: { status?: string; type?: string; source?: string }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.type) qs.set("type", params.type);
  if (params?.source) qs.set("source", params.source);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return http<{ count: number; requests: HubRequest[] }>(`/api/v1/requests${suffix}`);
}

export function acceptRequest(id: string) {
  return http<{ accepted: boolean; auto_reject_reason: string | null; request: HubRequest }>(
    `/api/v1/requests/${id}/accept`,
    { method: "POST" },
  );
}

export function rejectRequest(id: string, reason: string) {
  return http<HubRequest>(`/api/v1/requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function listPlans() {
  return http<{ count: number; plans: Plan[] }>("/api/v1/plans");
}

export function listActivity(limit = 50) {
  return http<{ activity: ActivityEntry[] }>(`/api/v1/agent-activity?limit=${limit}`);
}