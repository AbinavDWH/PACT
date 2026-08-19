"use client";

import { useEffect, useState } from "react";
import { listOrganizations, listRequests } from "../../lib/api";
import { HubRequest, Organization, RESOURCE_CODE_LABELS } from "../../lib/types";
import AgentLog from "../../components/AgentLog";

const MATCHED_STATUSES = ["matched", "allocated", "completed"];

function coverageColor(pct: number) {
  if (pct >= 100) return "text-[#4CAF50]";
  if (pct >= 50) return "text-[#FF9800]";
  return "text-[#F62440]";
}

export default function MatchingPage() {
  const [needs, setNeeds] = useState<HubRequest[]>([]);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [reqRes, orgRes] = await Promise.all([
          listRequests({ type: "need" }),
          listOrganizations(),
        ]);
        if (!mounted) return;
        setNeeds(reqRes.requests);
        setOrgs(orgRes.organizations);
        setError(null);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Backend unreachable");
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const activeNeeds = needs.filter((n) => !["rejected", "duplicate"].includes(n.status));
  const matchedNeeds = activeNeeds.filter((n) => MATCHED_STATUSES.includes(n.status));
  const totalMatchedUnits = matchedNeeds.reduce((sum, n) => sum + (n.total_matched ?? 0), 0);

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            Resource Matching Agent
          </p>
          <h1 className="mt-1 text-3xl font-bold">Requirement → Provider Matching</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Accept a need in the Request Hub — the Resource Matching Agent finds providers and
            results appear here live.
          </p>
        </header>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach the FastAPI backend ({error}). Start it with{" "}
            <code>uvicorn app.main:app --reload --host 0.0.0.0</code>.
          </div>
        )}

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#2b1a0e]">{activeNeeds.length}</div>
            <div className="text-sm text-[#7c6a58]">Active Needs</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#4CAF50]">{matchedNeeds.length}</div>
            <div className="text-sm text-[#7c6a58]">Needs Matched</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#2196F3]">{totalMatchedUnits}</div>
            <div className="text-sm text-[#7c6a58]">Total Units Matched</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#FF9800]">{orgs.length}</div>
            <div className="text-sm text-[#7c6a58]">Providers Online</div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          {/* LEFT: matching results */}
          <div className="space-y-4">
            {activeNeeds.length === 0 ? (
              <div className="rounded-xl border border-[#FFE5BF] bg-white p-8 text-center text-[#a1866f]">
                No active needs. Submit a field report or use the SMS simulator.
              </div>
            ) : (
              activeNeeds.map((need) => {
                const matches = need.matches ?? [];
                const required = need.quantity ?? 0;
                const matched = need.total_matched ?? 0;
                const pct = required > 0 ? Math.min(100, Math.round((matched / required) * 100)) : 0;
                const isMatched = MATCHED_STATUSES.includes(need.status);
                const isPending = ["pending", "accepted", "processing"].includes(need.status);

                return (
                  <div key={need.id} className="rounded-xl border border-[#FFE5BF] bg-white p-6">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-lg font-bold">{need.id}</h3>
                          <span className="rounded-full bg-[#FFF2DB] px-2 py-0.5 text-xs font-semibold text-[#7c4a12]">
                            {need.source}
                          </span>
                        </div>
                        <p className="text-sm text-[#7c6a58]">
                          {need.resource} × {required} → {need.location_name ?? need.location_code}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className={`text-xl font-bold ${coverageColor(pct)}`}>{pct}%</div>
                        <div className="text-xs text-[#a1866f]">coverage</div>
                      </div>
                    </div>

                    {/* coverage bar */}
                    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[#FFF2DB]">
                      <div
                        className={`h-full transition-all ${pct >= 100 ? "bg-[#4CAF50]" : "bg-[#F62440]"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    {/* status line */}
                    <div className="mt-3 text-sm">
                      {isPending && (
                        <span className="text-[#FF9800] font-semibold">
                          {need.status === "pending"
                            ? "Waiting for coordinator approval — click Accept in the Request Hub"
                            : need.status === "accepted"
                            ? "Agent pipeline starting…"
                            : "Need Assessment Agent working…"}
                        </span>
                      )}
                      {isMatched && (
                        <span className="text-[#4CAF50] font-semibold">
                          Matched {matched} of {required} units from {matches.length} provider
                          {matches.length === 1 ? "" : "s"}
                        </span>
                      )}
                    </div>

                    {/* matched providers */}
                    {isMatched && matches.length > 0 && (
                      <div className="mt-4">
                        <div className="text-xs font-semibold uppercase text-[#7c4a12]">
                          Matched Providers
                        </div>
                        <div className="mt-2 space-y-2">
                          {matches.map((m, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between rounded-lg bg-[#FFFAF3] px-3 py-2 text-sm"
                            >
                              <span className="font-medium">{m.organization_id}</span>
                              <div className="flex gap-4">
                                <span className="font-mono">{m.quantity} units available</span>
                                <span className="text-[#a1866f]">ETA: {m.eta_hours}h</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {isMatched && matches.length === 0 && (
                      <div className="mt-4 rounded-lg border border-dashed border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
                        No providers found with this resource — needs replanning or new providers.
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* RIGHT: provider inventory (shared profiles) */}
          <div className="space-y-4">
            <div className="rounded-xl border border-[#FFE5BF] bg-white">
              <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
                <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
                  Provider Inventory (shared profile)
                </h2>
                <p className="mt-1 text-[11px] text-[#a1866f]">
                  Donor, staff, and warehouse data withheld by Privacy Filter
                </p>
              </div>
              <div className="space-y-3 p-4">
                {orgs.length === 0 && (
                  <p className="text-sm text-[#a1866f]">No providers registered.</p>
                )}
                {orgs.map((org) => (
                  <div key={org.organization_id} className="rounded-lg bg-[#FFFAF3] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold">{org.organization_id}</span>
                      <span className="text-xs text-[#a1866f]">
                        ETA ~{org.eta_hours}h · {org.radius_km} km
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {Object.entries(org.resources).length === 0 && (
                        <span className="text-xs text-[#a1866f]">No stock</span>
                      )}
                      {Object.entries(org.resources).map(([code, qty]) => (
                        <span
                          key={code}
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            qty > 0 ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {RESOURCE_CODE_LABELS[code] ?? code}: {qty}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <AgentLog />
          </div>
        </div>
      </div>
    </main>
  );
}