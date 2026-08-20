"use client";

import { useEffect, useState } from "react";
import { confirmHandover, confirmReceipt, createRequest, listPlans, listRequests } from "../../lib/api";
import { HubRequest, Plan } from "../../lib/types";
import { getSession, UserSession } from "../../lib/auth";

const LOCATIONS = [
  { code: "RA", label: "RA — Region A" },
  { code: "RB", label: "RB — Region B" },
  { code: "RC", label: "RC — Region C" },
  { code: "D1", label: "D1 — District North" },
  { code: "D2", label: "D2 — District South" },
];

const RESOURCES = [
  { code: "M", label: "Medical kits" },
  { code: "F", label: "Food kits" },
  { code: "W", label: "Water kits" },
  { code: "T", label: "Tents" },
  { code: "B", label: "Blankets" },
  { code: "H", label: "Hygiene kits" },
  { code: "D", label: "Medical teams" },
];

const URGENCIES = [
  { code: "L", label: "Low" },
  { code: "M", label: "Medium" },
  { code: "H", label: "High" },
  { code: "C", label: "Critical" },
];

const AVAILABILITY = [
  { code: "A", label: "Available" },
  { code: "L", label: "Limited" },
  { code: "U", label: "Unavailable" },
];

const inputClass =
  "mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F62440]";
const labelClass = "text-sm font-semibold text-[#7c4a12]";

function statusBadge(s: string) {
  if (s === "pending") return "bg-orange-100 text-orange-700";
  if (["accepted", "processing", "matched", "allocated", "completed"].includes(s))
    return "bg-green-100 text-green-700";
  if (["rejected", "duplicate"].includes(s)) return "bg-red-100 text-red-700";
  return "bg-[#FFF2DB] text-[#7c4a12]";
}

export default function DonorPage() {
  const [session, setSessionState] = useState<UserSession | null>(null);
  // Shared organization identity
  const [orgId, setOrgId] = useState("DONOR01");

  // Register Resource form
  const [resResource, setResResource] = useState("M");
  const [resQuantity, setResQuantity] = useState("200");
  const [resLocation, setResLocation] = useState("RA");
  const [resAvailability, setResAvailability] = useState("A");

  // File Need form
  const [needResource, setNeedResource] = useState("F");
  const [needQuantity, setNeedQuantity] = useState("300");
  const [needLocation, setNeedLocation] = useState("RA");
  const [needUrgency, setNeedUrgency] = useState("H");

  const [result, setResult] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [submissions, setSubmissions] = useState<HubRequest[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [actionBusyId, setActionBusyId] = useState<string | null>(null);

  // Load session on mount
  useEffect(() => {
    const s = getSession();
    if (s) {
      setSessionState(s);
      setOrgId(s.organizationId);
    }
  }, []);

  // Live: this org's submissions & assigned plans (poll every 3s)
  useEffect(() => {
    const org = orgId.trim().toUpperCase();
    if (!org) {
      setSubmissions([]);
      setPlans([]);
      return;
    }
    let mounted = true;
    const load = async () => {
      try {
        const [reqRes, planRes] = await Promise.all([listRequests(), listPlans()]);
        if (!mounted) return;
        setSubmissions(reqRes.requests.filter((r) => r.organization_id === org));
        setPlans(
          planRes.plans.filter(
            (p) =>
              p.allocations.some((a) => a.organization_id === org) ||
              reqRes.requests.some((r) => r.organization_id === org && r.plan_id === p.plan_id)
          )
        );
      } catch {
        // backend unreachable — keep last state
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [orgId]);

  const handleConfirmHandover = async (planId?: string, requestId?: string) => {
    const idKey = planId || requestId || "action";
    setActionBusyId(idKey);
    try {
      const res = await confirmHandover({
        plan_id: planId,
        request_id: requestId,
        organization_id: orgId.trim().toUpperCase(),
      });
      setResult({
        kind: "success",
        text: res.message || "Handover confirmed! Status updated to In Transit (Dispatched).",
      });
      // reload
      const [reqRes, planRes] = await Promise.all([listRequests(), listPlans()]);
      const org = orgId.trim().toUpperCase();
      setSubmissions(reqRes.requests.filter((r) => r.organization_id === org));
      setPlans(
        planRes.plans.filter(
          (p) =>
            p.allocations.some((a) => a.organization_id === org) ||
            reqRes.requests.some((r) => r.organization_id === org && r.plan_id === p.plan_id)
        )
      );
    } catch (e) {
      setResult({ kind: "error", text: e instanceof Error ? e.message : "Handover confirmation failed" });
    } finally {
      setActionBusyId(null);
    }
  };

  const handleConfirmReceipt = async (planId?: string, requestId?: string) => {
    const idKey = planId || requestId || "action";
    setActionBusyId(idKey);
    try {
      const res = await confirmReceipt({
        plan_id: planId,
        request_id: requestId,
        organization_id: orgId.trim().toUpperCase(),
      });
      setResult({
        kind: "success",
        text: res.message || "Receipt confirmed! Supplies marked as Received / Delivered.",
      });
      // reload
      const [reqRes, planRes] = await Promise.all([listRequests(), listPlans()]);
      const org = orgId.trim().toUpperCase();
      setSubmissions(reqRes.requests.filter((r) => r.organization_id === org));
      setPlans(
        planRes.plans.filter(
          (p) =>
            p.allocations.some((a) => a.organization_id === org) ||
            reqRes.requests.some((r) => r.organization_id === org && r.plan_id === p.plan_id)
        )
      );
    } catch (e) {
      setResult({ kind: "error", text: e instanceof Error ? e.message : "Receipt confirmation failed" });
    } finally {
      setActionBusyId(null);
    }
  };

  const submitResource = async () => {
    setSending(true);
    setResult(null);
    try {
      const org = orgId.trim().toUpperCase();
      if (!org) throw new Error("Organization ID is required");
      const qty = parseInt(resQuantity, 10);
      if (!qty || qty <= 0) throw new Error("Quantity must be a positive number");

      const created = await createRequest({
        type: "resource",
        organization_id: org,
        location: resLocation,
        resource: resResource,
        quantity: qty,
        availability_status: resAvailability,
        source: "web",
      });
      setResult({
        kind: "success",
        text: `Resource registered as ${created.id} — now visible to the Resource Matching Agent.`,
      });
    } catch (e) {
      setResult({ kind: "error", text: e instanceof Error ? e.message : "Failed to register resource" });
    } finally {
      setSending(false);
    }
  };

  const submitNeed = async () => {
    setSending(true);
    setResult(null);
    try {
      const org = orgId.trim().toUpperCase();
      if (!org) throw new Error("Organization ID is required");
      const qty = parseInt(needQuantity, 10);
      if (!qty || qty <= 0) throw new Error("Quantity must be a positive number");

      const created = await createRequest({
        type: "need",
        organization_id: org,
        location: needLocation,
        resource: needResource,
        quantity: qty,
        urgency: needUrgency,
        source: "web",
      });
      setResult({
        kind: "success",
        text: `Need filed as ${created.id} — awaiting coordinator approval in the Request Hub.`,
      });
    } catch (e) {
      setResult({ kind: "error", text: e instanceof Error ? e.message : "Failed to file need" });
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            Donor Portal
          </p>
          <h1 className="mt-1 text-3xl font-bold">Register Resources & Aid Donations</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Donate medical kits, food, water and supplies directly to the humanitarian network.
            All contributions are coordinated through privacy-preserving agents.
          </p>
        </header>

        {/* Authenticated donor organization identity */}
        <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <label className={labelClass}>Organization Identity</label>
              <div className="mt-1 flex items-center gap-3">
                <input
                  type="text"
                  value={orgId}
                  disabled={session !== null}
                  onChange={(e) => setOrgId(e.target.value.toUpperCase())}
                  placeholder="DONOR01"
                  className={`w-full max-w-sm rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#F62440] ${
                    session ? "bg-[#FFF8E7] text-[#7c4a12] cursor-not-allowed" : "bg-white"
                  }`}
                />
                {session && (
                  <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-bold text-green-800">
                    Verified Donor Session
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-[#a1866f]">
                {session
                  ? `Authenticated as ${session.displayName} (${session.organizationId}). Access restricted to your organization's submissions.`
                  : "Used for both forms. Your submissions appear below and on the Request Hub."}
              </p>
            </div>
          </div>
        </div>

        {/* Result banner */}
        {result && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              result.kind === "success"
                ? "border-green-300 bg-green-50 text-green-800"
                : "border-red-300 bg-red-50 text-red-700"
            }`}
          >
            {result.text}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          {/* ── Register Resource (donate) ── */}
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-[#4CAF50]" />
              <h2 className="text-lg font-bold">Register a Resource (Donate)</h2>
            </div>
            <p className="mt-1 text-sm text-[#7c6a58]">
              Makes your stock available to the Resource Matching Agent.
            </p>

            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Resource Type</label>
                <select value={resResource} onChange={(e) => setResResource(e.target.value)} className={inputClass}>
                  {RESOURCES.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass}>Quantity</label>
                <input
                  type="number"
                  min="1"
                  value={resQuantity}
                  onChange={(e) => setResQuantity(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Location</label>
                <select value={resLocation} onChange={(e) => setResLocation(e.target.value)} className={inputClass}>
                  {LOCATIONS.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass}>Availability</label>
                <select
                  value={resAvailability}
                  onChange={(e) => setResAvailability(e.target.value)}
                  className={inputClass}
                >
                  {AVAILABILITY.map((a) => (
                    <option key={a.code} value={a.code}>
                      {a.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={submitResource}
              disabled={sending}
              className="mt-5 w-full rounded-lg bg-[#4CAF50] px-4 py-3 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-50"
            >
              {sending ? "Registering…" : "Register Resource"}
            </button>
          </div>

          {/* ── File Need (request) ── */}
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-[#F62440]" />
              <h2 className="text-lg font-bold">File a Need (Request)</h2>
            </div>
            <p className="mt-1 text-sm text-[#7c6a58]">
              Sent to the Request Hub for coordinator approval, then matched with providers.
            </p>

            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Resource Type</label>
                <select value={needResource} onChange={(e) => setNeedResource(e.target.value)} className={inputClass}>
                  {RESOURCES.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass}>Quantity</label>
                <input
                  type="number"
                  min="1"
                  value={needQuantity}
                  onChange={(e) => setNeedQuantity(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Location</label>
                <select value={needLocation} onChange={(e) => setNeedLocation(e.target.value)} className={inputClass}>
                  {LOCATIONS.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass}>Urgency</label>
                <select value={needUrgency} onChange={(e) => setNeedUrgency(e.target.value)} className={inputClass}>
                  {URGENCIES.map((u) => (
                    <option key={u.code} value={u.code}>
                      {u.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={submitNeed}
              disabled={sending}
              className="mt-5 w-full rounded-lg bg-[#F62440] px-4 py-3 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-50"
            >
              {sending ? "Filing…" : "File Need"}
            </button>
          </div>
        </div>

        {/* ── Active Aid Allocations & Handover Queue ── */}
        <div className="rounded-xl border border-[#FFE5BF] bg-white">
          <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3 flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
              Active Aid Allocations & Handover Queue ({plans.length})
            </h2>
            <span className="text-xs text-[#7c6a58]">
              Confirm handover when supplies are dispatched to the field
            </span>
          </div>
          <div className="p-4 space-y-3">
            {plans.length === 0 ? (
              <p className="text-sm text-[#a1866f] py-4 text-center">
                No active aid allocations assigned to {orgId.trim().toUpperCase() || "your organization"} yet.
              </p>
            ) : (
              plans.map((p) => {
                const myAllocations = p.allocations.filter((a) => a.organization_id === orgId.trim().toUpperCase());
                const myTotalQty = myAllocations.reduce((acc, a) => acc + a.quantity, 0) || p.allocated_quantity;
                const isHandedOver = ["in_transit", "dispatched", "delivered", "completed"].includes(p.status);
                const isDelivered = ["delivered", "completed"].includes(p.status);

                return (
                  <div
                    key={p.plan_id}
                    className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[#FFE5BF] bg-[#FFFAF3] p-4"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[#2b1a0e]">{p.plan_id}</span>
                        <span className="text-xs text-[#7c6a58]">· {p.resource}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            isDelivered
                              ? "bg-green-100 text-green-700"
                              : isHandedOver
                              ? "bg-purple-100 text-purple-700"
                              : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          {p.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-[#7c6a58]">
                        Destination: <strong className="text-[#2b1a0e]">{p.location_name ?? p.location_code}</strong> · Quantity:{" "}
                        <strong className="text-[#2b1a0e] font-mono">{myTotalQty} units</strong>
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {!isHandedOver ? (
                        <button
                          onClick={() => handleConfirmHandover(p.plan_id, p.request_id || undefined)}
                          disabled={actionBusyId === p.plan_id}
                          className="rounded-lg bg-[#4CAF50] px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
                        >
                          {actionBusyId === p.plan_id ? "Confirming…" : "✓ Confirm Handed Over"}
                        </button>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="rounded-lg bg-green-100 px-3 py-1.5 text-xs font-bold text-green-800">
                            ✓ Handed Over Success
                          </span>
                          {!isDelivered && (
                            <button
                              onClick={() => handleConfirmReceipt(p.plan_id, p.request_id || undefined)}
                              disabled={actionBusyId === p.plan_id}
                              className="rounded-lg bg-[#2196F3] px-3 py-1.5 text-xs font-bold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
                            >
                              {actionBusyId === p.plan_id ? "Confirming…" : "Confirm Received"}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Your Submissions (live) ── */}
        <div className="rounded-xl border border-[#FFE5BF] bg-white">
          <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
            <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
              Your Submissions ({submissions.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#FFE5BF] bg-[#FFFAF3] text-left text-xs uppercase tracking-wide text-[#7c4a12]">
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Resource</th>
                  <th className="px-4 py-3">Qty</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {submissions.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-[#a1866f]">
                      No submissions yet for {orgId.trim().toUpperCase() || "your organization"}.
                    </td>
                  </tr>
                ) : (
                  submissions.map((r) => {
                    const isHandedOver = ["in_transit", "dispatched", "delivered", "completed"].includes(r.status);
                    const isDelivered = ["delivered", "completed"].includes(r.status);

                    return (
                      <tr key={r.id} className="border-b border-[#FFF2DB] last:border-0 hover:bg-[#FFFAF3]">
                        <td className="px-4 py-3 font-semibold">{r.id}</td>
                        <td className="px-4 py-3 capitalize">{r.type}</td>
                        <td className="px-4 py-3">{r.resource ?? "—"}</td>
                        <td className="px-4 py-3 font-mono">{r.quantity}</td>
                        <td className="px-4 py-3">{r.location_name ?? r.location_code}</td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadge(r.status)}`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-[#a1866f]">{r.created_at}</td>
                        <td className="px-4 py-3">
                          {r.type === "resource" ? (
                            !isHandedOver ? (
                              <button
                                onClick={() => handleConfirmHandover(r.plan_id || undefined, r.id)}
                                disabled={actionBusyId === r.id}
                                className="rounded-lg bg-[#4CAF50] px-3 py-1 text-xs font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                              >
                                {actionBusyId === r.id ? "…" : "Confirm Handed"}
                              </button>
                            ) : (
                              <span className="text-xs font-semibold text-green-700">✓ Handed</span>
                            )
                          ) : r.type === "need" ? (
                            !isDelivered ? (
                              <button
                                onClick={() => handleConfirmReceipt(r.plan_id || undefined, r.id)}
                                disabled={actionBusyId === r.id}
                                className="rounded-lg bg-[#2196F3] px-3 py-1 text-xs font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                              >
                                {actionBusyId === r.id ? "…" : "Confirm Received"}
                              </button>
                            ) : (
                              <span className="text-xs font-semibold text-green-700">✓ Received</span>
                            )
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
      </div>
    </main>
  );
}