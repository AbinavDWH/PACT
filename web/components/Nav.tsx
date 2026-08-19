"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { UserSession, getSession, clearSession, getRoleLabel, canAccess } from "../lib/auth";

const ALL_NAV_ITEMS = [
  { href: "/requests", label: "Command Center" },
  { href: "/donor", label: "Donor Portal" },
  { href: "/needs", label: "Needs" },
  { href: "/matching", label: "Matching" },
  { href: "/resources", label: "Resources" },
  { href: "/plans", label: "Plans" },
  { href: "/map", label: "Map" },
  { href: "/privacy", label: "Privacy" },
  { href: "/sms", label: "SMS" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSessionState] = useState<UserSession | null>(null);

  useEffect(() => {
    const s = getSession();
    setSessionState(s);

    if (!s && pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, router]);

  const handleLogout = () => {
    clearSession();
    setSessionState(null);
    router.push("/login");
  };

  if (pathname === "/login" || !session) {
    return null;
  }

  // FILTER nav items based on role
  const visibleNavItems = ALL_NAV_ITEMS.filter((item) =>
    canAccess(item.href, session.role)
  );

  return (
    <nav className="border-b border-[#FFE5BF] bg-white">
      <div className="mx-auto max-w-[1600px] px-6">
        <div className="flex h-14 items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <Link href="/requests" className="text-lg font-bold text-[#F62440]">
              PACT
            </Link>
            <div className="flex gap-1 overflow-x-auto">
              {visibleNavItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${
                      isActive
                        ? "bg-[#F62440] text-white"
                        : "text-[#7c4a12] hover:bg-[#FFF2DB]"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm font-semibold text-[#2b1a0e]">
                {session.displayName}
              </div>
              <div className="text-xs text-[#7c6a58]">
                {getRoleLabel(session.role)} · {session.organizationId}
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-[#e3c9a8] px-3 py-1.5 text-sm font-semibold text-[#7c4a12] transition hover:bg-[#FFF2DB]"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}