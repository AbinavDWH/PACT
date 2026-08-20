"use client";

// One header for every console section.
//
// The console used to be a single scrolling page with two links. A jury landing
// on it had to know that the map, the deliberation and the privacy boundary
// were all somewhere inside one long card. These are named sections instead.
//
// They are routes, not local tabs, but the socket lives in admin/layout.tsx —
// so moving between them does NOT interrupt a running deliberation. That
// matters: splitting a live stream across pages would otherwise mean losing it
// halfway through, which is exactly when a juror wants to look at the map.

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS = [
  { href: "/admin", label: "Deliberation", hint: "Watch the agents decide" },
  { href: "/admin/agents", label: "Agents", hint: "What the ten agents are, and which of them is a model" },
  { href: "/admin/map", label: "Map", hint: "Where the request and helpers are" },
  { href: "/admin/privacy", label: "Privacy", hint: "What was hidden, and from whom" },
  { href: "/admin/requests", label: "Requests", hint: "Everything received so far" },
];

export default function ConsoleNav({
  connected,
  eventCount,
}: {
  connected: boolean;
  eventCount: number;
}) {
  const pathname = usePathname();

  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label="PACT home">
        <span className="mark">PACT</span>
        <span className="sub">Admin Console</span>
      </Link>

      <nav className="nav" aria-label="Console sections">
        {SECTIONS.map((s) => {
          const active = pathname === s.href;
          return (
            <Link
              key={s.href}
              href={s.href}
              title={s.hint}
              className={`navItem ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {s.label}
            </Link>
          );
        })}
      </nav>

      {/* role=status so a screen reader hears the socket drop rather than only
          seeing the dot change colour. */}
      <div className="status" role="status" aria-live="polite">
        <span className={`dot ${connected ? "on" : "off"}`} aria-hidden="true" />
        {connected ? "connected" : "reconnecting"}
        <span className="count">{eventCount.toLocaleString()} events</span>
      </div>
    </header>
  );
}
