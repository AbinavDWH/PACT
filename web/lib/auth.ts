export type UserRole = "admin" | "donor_group" | "individual";

export interface UserSession {
  role: UserRole;
  organizationId: string;
  displayName: string;
}

const AUTH_KEY = "pact_web_session";

export function getSession(): UserSession | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem(AUTH_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as UserSession;
  } catch {
    return null;
  }
}

export function setSession(session: UserSession): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AUTH_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_KEY);
}

export function getRoleLabel(role: UserRole): string {
  return {
    admin: "Administrator",
    donor_group: "Donor Group",
    individual: "Individual",
  }[role];
}