"use client";

import { useEffect, useState } from "react";
import { listRequests } from "../../lib/api";
import { HubRequest } from "../../lib/types";
import AgentLog from "../../components/AgentLog";

const availabilityBadge = (a?: string) => {
  const v = (a ?? "").toLowerCase();
  if (v === "available") return "bg-green-100 text-green-700";
  if (v === "limited") return "bg-yellow-100 text-yellow-700";
  return "bg-red-100 text-red-700";
};

export default function ResourcesPage() {
  const [resources, setResources] = useState<HubRequest[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await listRequests({ type: "resource" });
        if (!mounted) return;
        setResources(res.requests);
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

  const available = resources.filter((r) => (r.availability ?? "").toLowerCase() === "available").length;
  const limited = resources.filter((r) => (r.availability ?? "").toLowerCase() === "limited").length;

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            Shared Resources
          </p>
          <h1 className="mt-1 text-3xl font-bold">Post-Privacy Resource Visibility</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Only safe fields (type, quantity, region) — donor, staff, and warehouse data withheld by the Privacy Filter Agent.
          </p>
        </header>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach the FastAPI backend ({error}). Start it with{" "}
            <code>uvicorn app.main:app --reload --host 0.0.0.0</code>.
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#2b1a0e]">{resources.length}</div>
            <div className="text-sm text-[#7c6a58]">Total Resource Listings</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#4CAF50]">{available}</div>
            <div className="text-sm text-[#7c6a58]">Available</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#FF9800]">{limited}</div>
            <div className="text-sm text-[#7c6a58]">Limited</div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="rounded-xl border border-[#FFE5BF] bg-white">
            <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
              <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
                Organization Availability ({resources.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#FFE5BF] bg-[#FFFAF3] text-left text-xs uppercase tracking-wide text-[#7c4a12]">
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Organization</th>
                    <th className="px-4 py-3">Location</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Quantity</th>
                    <th className="px-4 py-3">Availability</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {resources.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-[#a1866f]">
                        No resources registered yet.
                      </td>
                    </tr>
                  ) : (
                    resources.map((r) => (
                      <tr
                        key={r.id}
                        className="border-b border-[#FFF2DB] last:border-0 hover:bg-[#FFFAF3]"
                      >
                        <td className="px-4 py-3 font-semibold">{r.id}</td>
                        <td className="px-4 py-3 font-medium">{r.organization_id}</td>
                        <td className="px-4 py-3">{r.location_name ?? r.location_code}</td>
                        <td className="px-4 py-3">{r.resource}</td>
                        <td className="px-4 py-3 font-mono">{r.quantity}</td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${availabilityBadge(r.availability)}`}>
                            {r.availability}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-lg bg-[#FFF2DB] px-2 py-1 text-xs font-semibold text-[#7c4a12]">
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-[#a1866f]">{r.source}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <AgentLog />
        </div>
      </div>
    </main>
  );
}