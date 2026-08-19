"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityEntry, HubRequest } from "../../lib/types";
import { acceptRequest, listActivity, listRequests, rejectRequest } from "../../lib/api";
import RequestTable from "../../components/RequestTable";

type TabKey = "all" | "pending" | "accepted" | "rejected";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "accepted", label: "Accepted" },
  { key: "rejected", label: "Rejected" },
];

const ACCEPTED_FAMILY = new Set(["accepted", "processing", "matched", "allocated", "completed"]);
const REJECTED_FAMILY = new Set(["rejected", "duplicate"]);

export default function RequestsPage() {
  const [requests, setRequests] = useState<HubRequest[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [tab, setTab] = useState<TabKey>("all");
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [reqRes, actRes] = await Promise.all([listRequests(), listActivity(12)]);
      setRequests(reqRes.requests);
      setActivity(actRes.activity);
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend unreachable");
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);

  const counts = useMemo(() => ({
    all: requests.length,
    pending: requests.filter((r) => r.status === "pending").length,
    accepted: requests.filter((r) => ACCEPTED_FAMILY.has(r.status)).length,
    rejected: requests.filter((r) => REJECTED_FAMILY.has(r.status)).length,
  }), [requests]);

  const visible = useMemo(() => {
    if (tab === "pending") return requests.filter((r) => r.status === "pending");
    if (tab === "accepted") return requests.filter((r) => ACCEPTED_FAMILY.has(r.status));
    if (tab === "rejected") return requests.filter((r) => REJECTED_FAMILY.has(r.status));
    return requests;
  }, [requests, tab]);

  const onAccept = useCallback(async (id: string) => {
    setBusyId(id);
    try {
      const result = await acceptRequest(id);
      if (!result.accepted) {
        window.alert(`Auto-rejected by validation: ${result.auto_reject_reason}`);
      }
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Accept failed");
    } finally {
      setBusyId(null);
    }
  }, [refresh]);

  const onReject = useCallback(async (id: string) => {
    const reason = window.prompt("Reject reason (invalid / duplicate / privacy):", "invalid");
    if (reason === null) return;
    setBusyId(id);
    try {
      await rejectRequest(id, reason.trim() || "invalid");
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusyId(null);
    }
  }, [refresh]);

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">PACT Command Center</p>
            <h1 className="mt-1 text-3xl font-bold">Request Hub</h1>
            <p className="mt-1 max-w-2xl text-sm text-[#7c6a58]">
              Every request — web, SMS, or Android — flows through the same privacy-checked acceptance pipeline.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#7c6a58]">
            <span className={`h-2 w-2 rounded-full ${error ? "bg-red-500" : "animate-pulse bg-green-500"}`} />
            {error ? "Backend unreachable" : lastUpdated ? `Live · updated ${lastUpdated.toLocaleTimeString()}` : "Connecting…"}
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach the FastAPI backend ({error}). Start it with <code>uvicorn app.main:app --reload</code> on port 8000.
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                tab === t.key ? "bg-[#F62440] text-white" : "bg-[#FFF2DB] text-[#7c4a12] hover:bg-[#FFE5BF]"
              }`}
            >
              {t.label} ({counts[t.key]})
            </button>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <RequestTable requests={visible} busyId={busyId} onAccept={onAccept} onReject={onReject} />

          <aside className="h-fit rounded-xl border border-[#FFE5BF] bg-white">
            <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
              <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">Agent Activity</h2>
            </div>
            <ul className="max-h-[520px] space-y-3 overflow-y-auto px-4 py-4">
              {activity.length === 0 && (
                <li className="text-sm text-[#a1866f]">No agent activity yet.</li>
              )}
              {activity.map((a, i) => (
                <li key={`${a.ts}-${i}`} className="text-xs leading-relaxed">
                  <div className="font-mono text-[10px] text-[#a1866f]">
                    {new Date(a.ts).toLocaleTimeString()}
                  </div>
                  <div>
                    <span className="font-semibold text-[#F62440]">{a.agent}</span>{" "}
                    <span className="text-[#4a3a28]">{a.message}</span>
                  </div>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    </main>
  );
}