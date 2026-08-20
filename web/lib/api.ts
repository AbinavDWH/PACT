import {
  ActivityEntry,
  CreateRequestBody,
  HubRequest,
  LiveLocation,
  Organization,
  Plan,
} from "./types";

// Backend on the same machine as the web dashboard → localhost
const API_URL = "http://localhost:8000";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const res = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error("Backend not responding (5s timeout)");
    }
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

export function listRequests(params?: { status?: string; type?: string; source?: string }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.type) qs.set("type", params.type);
  if (params?.source) qs.set("source", params.source);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return http<{ count: number; requests: HubRequest[] }>(`/api/v1/requests${suffix}`);
}

// NEW: Donor Portal — register a resource or file a need
export function createRequest(body: CreateRequestBody) {
  return http<HubRequest>("/api/v1/requests", {
    method: "POST",
    body: JSON.stringify(body),
  });
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

export function confirmHandover(body: {
  plan_id?: string;
  request_id?: string;
  organization_id?: string;
  notes?: string;
}) {
  return http<{ status: string; message: string; plan?: Plan; request?: HubRequest }>(
    "/api/v1/handoff/confirm",
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}

export function confirmReceipt(body: {
  plan_id?: string;
  request_id?: string;
  organization_id?: string;
  notes?: string;
}) {
  return http<{ status: string; message: string; plan?: Plan; request?: HubRequest }>(
    "/api/v1/delivery/confirm",
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}

export function listActivity(limit = 50) {
  return http<{ activity: ActivityEntry[] }>(`/api/v1/agent-activity?limit=${limit}`);
}

export function listLocations() {
  return http<{ locations: LiveLocation[] }>("/api/v1/locations");
}

export function listOrganizations() {
  return http<{ organizations: Organization[] }>("/api/v1/organizations");
}