"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSession, getRoleHome } from "../lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.push("/login");
    } else {
      // Redirect to role-specific home page
      router.push(getRoleHome(session.role));
    }
  }, [router]);

  return null;
}