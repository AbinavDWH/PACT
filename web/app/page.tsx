"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSession } from "../lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.push("/login");
    } else {
      router.push("/requests");
    }
  }, [router]);

  return null;
}