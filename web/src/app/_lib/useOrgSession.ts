"use client";

// Organization session.
//
// Unlike the admin console, this one does NOT sign in with baked-in
// credentials: which organization you are is the whole point of the screen, and
// the boundary being demonstrated is that an org sees only its own slice. A
// real login is the demonstration.
//
// The session lives in sessionStorage, which is an external store, so it is
// read through useSyncExternalStore rather than copied into state by a mount
// effect. The effect version worked but wrote state during mount on every load,
// and it meant two sources of truth for the same value.

import { useCallback, useSyncExternalStore } from "react";
import { API_BASE } from "./useAgentSocket";

const KEY = "pact.org.session";

export interface OrgSession {
  token: string;
  org_id: string;
  org_name: string;
  group_code: string;
}

// ---------------------------------------------------------------------------
// The store
// ---------------------------------------------------------------------------

const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  // Another tab signing in or out is a real event worth following: the two
  // tabs share sessionStorage per-tab, but `storage` still fires for same-key
  // writes in some browsers and costs nothing to listen for.
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

function readRaw(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

// getSnapshot must return a referentially stable value or React re-renders
// forever, so the parsed object is cached against the raw string it came from.
let cachedRaw: string | null = null;
let cached: OrgSession | null = null;
let primed = false;

function getSnapshot(): OrgSession | null {
  const raw = readRaw();
  if (!primed || raw !== cachedRaw) {
    primed = true;
    cachedRaw = raw;
    try {
      cached = raw ? (JSON.parse(raw) as OrgSession) : null;
    } catch {
      cached = null;
    }
  }
  return cached;
}

// There is no session on the server, and none during hydration.
function getServerSnapshot(): OrgSession | null {
  return null;
}

/** Read outside React (the fetch helper below needs it too). */
export function loadOrgSession(): OrgSession | null {
  if (typeof window === "undefined") return null;
  return getSnapshot();
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

// `ready` exists so the login form does not flash before storage has been
// consulted. Derived from hydration through the same mechanism -- false on the
// server, true on the client -- rather than from a mount effect setting state.
const noopSubscribe = () => () => {};
const alwaysTrue = () => true;
const alwaysFalse = () => false;

export function useOrgSession() {
  const session = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const ready = useSyncExternalStore(noopSubscribe, alwaysTrue, alwaysFalse);

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
    emit();
    return { ok: true as const };
  }, []);

  const logout = useCallback(() => {
    window.sessionStorage.removeItem(KEY);
    emit();
  }, []);

  return { session, ready, login, logout };
}
