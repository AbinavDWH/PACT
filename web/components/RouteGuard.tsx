"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getSession, canAccess, getRoleHome } from "../lib/auth";

export default function RouteGuard() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const session = getSession();

    // Not logged in → go to login
    if (!session) {
      router.push("/login");
      return;
    }

    // Logged in but trying to access a restricted page → redirect to their home
    if (!canAccess(pathname, session.role)) {
      router.push(getRoleHome(session.role));
    }
  }, [pathname, router]);

  return null;
}