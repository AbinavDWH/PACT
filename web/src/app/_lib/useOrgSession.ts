"use client";

// Organization session.
//
// Unlike the admin portal, this one does NOT log in silently with baked-in
// credentials: which organization you are is the whole point of the screen, and
// the boundary being demonstrated is that an org sees only its own slice. A
// real login is the demonstration.

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "./useAgentSocket";

const KEY = "pact.org.session";

export interface OrgSession {
  token: string;
  org_id: string;
  org_name: string;
  group_code: string;
}

export function loadOrgSession(): OrgSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as OrgSession) : null;
  } catch {
    return null;
  }
}

export async function orgFetch(path: string, session: OrgSession | null,
                               init: RequestInit = {}) {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
}

export function useOrgSession() {
  const [session, setSession] = useState<OrgSession | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSession(loadOrgSession());
    setReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/v1/org/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const j = (await res.json()) as Partial<OrgSession> & {
      status?: string; error?: string;
    };
    if (j.status !== "ok" || !j.token) {
      return { ok: false as const, error: j.error ?? "LOGIN_FAILED" };
    }
    const s: OrgSession = {
      token: j.token,
      org_id: j.org_id!,
      org_name: j.org_name ?? j.org_id!,
      group_code: j.group_code ?? "",
    };
    window.sessionStorage.setItem(KEY, JSON.stringify(s));
    setSession(s);
    return { ok: true as const };
  }, []);

  const logout = useCallback(() => {
    window.sessionStorage.removeItem(KEY);
    setSession(null);
  }, []);

  return { session, ready, login, logout };
}
