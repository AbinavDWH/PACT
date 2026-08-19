"use client";

import { useEffect, useState } from "react";
import { createRequest, listRequests } from "../../lib/api";
import { HubRequest } from "../../lib/types";

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

  // Live: this org's submissions (poll every 3s)
  useEffect(() => {
    const org = orgId.trim().toUpperCase();
    if (!org) {
      setSubmissions([]);
      return;
    }
    let mounted = true;
    const load = async () => {
      try {
        const res = await listRequests();
        if (!mounted) return;
        setSubmissions(res.requests.filter((r) => r.organization_id === org));
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
          <h1 className="mt-1 text-3xl font-bold">Register Resources & File Needs</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Donate medical kits, food, water and more — or request what your region needs.
            Everything flows through the same privacy-checked pipeline.
          </p>
        </header>

        {/* Shared organization identity */}
        <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
          <label className={labelClass}>Your Organization ID</label>
          <input
            type="text"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value.toUpperCase())}
            placeholder="DONOR01"
            className="mt-1 w-full max-w-sm rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#F62440]"
          />
          <p className="mt-1 text-xs text-[#a1866f]">
            Used for both forms. Your submissions appear below and on the Request Hub.
          </p>
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
                </tr>
              </thead>
              <tbody>
                {submissions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-[#a1866f]">
                      No submissions yet for {orgId.trim().toUpperCase() || "your organization"}.
                    </td>
                  </tr>
                ) : (
                  submissions.map((r) => (
                    <tr key={r.id} className="border-b border-[#FFF2DB] last:border-0 hover:bg-[#FFFAF3]">
                      <td className="px-4 py-3 font-semibold">{r.id}</td>
                      <td className="px-4 py-3 capitalize">{r.type}</td>
                      <td className="px-4 py-3">{r.resource ?? "—"}</td>
                      <td className="px-4 py-3 font-mono">
                        {r.type === "resource" ? r.quantity : r.quantity}
                      </td>
                      <td className="px-4 py-3">{r.location_name ?? r.location_code}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadge(r.status)}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-[#a1866f]">{r.created_at}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}