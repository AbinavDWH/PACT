"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
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

  return (
    <nav className="border-b border-[#FFE5BF] bg-white">
      <div className="mx-auto max-w-[1600px] px-6">
        <div className="flex h-14 items-center gap-6">
          <Link href="/requests" className="text-lg font-bold text-[#F62440]">
            PACT
          </Link>
          <div className="flex gap-1 overflow-x-auto">
            {NAV_ITEMS.map((item) => {
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
      </div>
    </nav>
  );
}