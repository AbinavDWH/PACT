export type UserRole = "admin" | "donor_group" | "individual";

export interface UserSession {
  role: UserRole;
  organizationId: string;
  displayName: string;
}

const AUTH_KEY = "pact_web_session";

// ═══════════════════════════════════════════════════════
// ROLE-BASED ACCESS CONTROL
// ═══════════════════════════════════════════════════════

const ALLOWED_ROUTES: Record<UserRole, string[]> = {
  admin: [
    "/requests",
    "/donor",
    "/needs",
    "/matching",
    "/resources",
    "/plans",
    "/map",
    "/privacy",
    "/sms",
  ],
  donor_group: [
    "/donor",
    "/resources",
    "/map",
  ],
  individual: [
    "/needs",
    "/map",
  ],
};

// Default landing page per role after login
const ROLE_HOME: Record<UserRole, string> = {
  admin: "/requests",
  donor_group: "/donor",
  individual: "/needs",
};

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

export function canAccess(route: string, role: UserRole): boolean {
  return ALLOWED_ROUTES[role]?.includes(route) ?? false;
}

export function getRoleHome(role: UserRole): string {
  return ROLE_HOME[role] ?? "/requests";
}

export function getAllowedRoutes(role: UserRole): string[] {
  return ALLOWED_ROUTES[role] ?? [];
}