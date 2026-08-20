"use client";

import { useEffect, useState } from "react";
import { confirmReceipt, listRequests } from "../../lib/api";
import { HubRequest } from "../../lib/types";
import AgentLog from "../../components/AgentLog";

const urgencyBadge = (u?: string | null) => {
  const v = (u ?? "").toLowerCase();
  if (v === "critical") return "bg-red-100 text-red-700";
  if (v === "high") return "bg-orange-100 text-orange-700";
  if (v === "medium") return "bg-yellow-100 text-yellow-700";
  return "bg-green-100 text-green-700";
};

const statusBadge = (s: string) => {
  if (s === "pending") return "bg-orange-100 text-orange-700";
  if (["accepted", "processing", "matched", "allocated"].includes(s))
    return "bg-blue-100 text-blue-700";
  if (["in_transit", "dispatched", "handed_over"].includes(s))
    return "bg-purple-100 text-purple-700";
  if (["delivered", "completed"].includes(s))
    return "bg-green-100 text-green-700";
  if (["rejected", "duplicate"].includes(s)) return "bg-red-100 text-red-700";
  return "bg-gray-100 text-gray-700";
};

export default function NeedsPage() {
  const [needs, setNeeds] = useState<HubRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await listRequests({ type: "need" });
        if (!mounted) return;
        setNeeds(res.requests);
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

  const handleConfirmReceipt = async (need: HubRequest) => {
    setBusyId(need.id);
    setSuccessMsg(null);
    try {
      const res = await confirmReceipt({
        plan_id: need.plan_id || undefined,
        request_id: need.id,
        organization_id: need.organization_id,
      });
      setSuccessMsg(res.message || `Need ${need.id} marked as received successfully!`);
      const reqRes = await listRequests({ type: "need" });
      setNeeds(reqRes.requests);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to confirm receipt");
    } finally {
      setBusyId(null);
    }
  };

  const pending = needs.filter((n) => n.status === "pending").length;
  const active = needs.filter((n) =>
    ["accepted", "processing", "matched", "allocated"].includes(n.status)
  ).length;
  const completed = needs.filter((n) => n.status === "completed").length;
  const critical = needs.filter((n) => (n.urgency ?? "").toLowerCase() === "critical").length;

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            Need Assessment
          </p>
          <h1 className="mt-1 text-3xl font-bold">Field Needs Coverage</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Live view of all need requests from field workers, SMS, and web intake.
          </p>
        </header>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach the FastAPI backend ({error}). Start it with{" "}
            <code>uvicorn app.main:app --reload --host 0.0.0.0</code>.
          </div>
        )}

        {successMsg && (
          <div className="rounded-lg border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800">
            ✓ {successMsg}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#F62440]">{critical}</div>
            <div className="text-sm text-[#7c6a58]">Critical Urgency</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#FF9800]">{pending}</div>
            <div className="text-sm text-[#7c6a58]">Pending Review</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#4CAF50]">{active}</div>
            <div className="text-sm text-[#7c6a58]">Active / Processing</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#2196F3]">{completed}</div>
            <div className="text-sm text-[#7c6a58]">Completed</div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="rounded-xl border border-[#FFE5BF] bg-white">
            <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
              <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
                All Needs ({needs.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#FFE5BF] bg-[#FFFAF3] text-left text-xs uppercase tracking-wide text-[#7c4a12]">
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Org</th>
                    <th className="px-4 py-3">Location</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Qty</th>
                    <th className="px-4 py-3">Urgency</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {needs.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-[#a1866f]">
                        No needs submitted yet.
                      </td>
                    </tr>
                  ) : (
                    needs.map((need) => {
                      const isDelivered = ["delivered", "completed"].includes(need.status);
                      const isAllocatedOrTransit = ["allocated", "matched", "in_transit", "dispatched", "handed_over"].includes(need.status);

                      return (
                        <tr
                          key={need.id}
                          className="border-b border-[#FFF2DB] last:border-0 hover:bg-[#FFFAF3]"
                        >
                          <td className="px-4 py-3 font-semibold">{need.id}</td>
                          <td className="px-4 py-3">{need.organization_id}</td>
                          <td className="px-4 py-3">{need.location_name ?? need.location_code}</td>
                          <td className="px-4 py-3">{need.resource}</td>
                          <td className="px-4 py-3 font-mono">{need.quantity}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${urgencyBadge(need.urgency)}`}>
                              {need.urgency}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadge(need.status)}`}>
                              {need.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-[#a1866f]">{need.source}</td>
                          <td className="px-4 py-3">
                            {isDelivered ? (
                              <span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-800">
                                ✓ Received Success
                              </span>
                            ) : isAllocatedOrTransit ? (
                              <button
                                onClick={() => handleConfirmReceipt(need)}
                                disabled={busyId === need.id}
                                className="rounded-lg bg-[#2196F3] px-3 py-1 text-xs font-bold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
                              >
                                {busyId === need.id ? "…" : "✓ Confirm Received"}
                              </button>
                            ) : (
                              <span className="text-xs text-[#a1866f]">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
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