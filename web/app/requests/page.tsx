"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { ActivityEntry, HubRequest } from "../../lib/types";
import {
  acceptRequest,
  aiTriageAllRequests,
  aiTriageRequest,
  confirmHandover,
  confirmReceipt,
  getAiTriageConfig,
  listActivity,
  listRequests,
  rejectRequest,
  setAiTriageConfig,
} from "../../lib/api";
import RequestTable from "../../components/RequestTable";

// FIX: load Leaflet map only in the browser (no SSR)
const ChennaiMap = dynamic(() => import("../../components/ChennaiMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center rounded-xl border border-[#FFE5BF] bg-white text-sm text-[#a1866f]">
      Loading Chennai map…
    </div>
  ),
});

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
  const [isTriagingAll, setIsTriagingAll] = useState(false);
  const [triageFeedback, setTriageFeedback] = useState<string | null>(null);
  const [autoTriageEnabled, setAutoTriageEnabled] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [reqRes, actRes, cfgRes] = await Promise.all([
        listRequests(),
        listActivity(12),
        getAiTriageConfig().catch(() => ({ enabled: true })),
      ]);
      setRequests(reqRes.requests);
      setActivity(actRes.activity);
      if (typeof cfgRes?.enabled === "boolean") {
        setAutoTriageEnabled(cfgRes.enabled);
      }
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
      if (!result.accepted) window.alert(`Auto-rejected: ${result.auto_reject_reason}`);
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

  const onAiTriage = useCallback(async (id: string) => {
    setBusyId(id);
    try {
      const result = await aiTriageRequest(id);
      setTriageFeedback(
        `AI Triage for ${id}: ${result.decision} (Confidence: ${Math.round(result.confidence * 100)}%) — ${result.reason}`
      );
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "AI Triage failed");
    } finally {
      setBusyId(null);
    }
  }, [refresh]);

  const onAiTriageAll = useCallback(async () => {
    setIsTriagingAll(true);
    try {
      const result = await aiTriageAllRequests();
      setTriageFeedback(result.message);
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "AI Batch Triage failed");
    } finally {
      setIsTriagingAll(false);
    }
  }, [refresh]);

  const onToggleAutoTriage = useCallback(async () => {
    const nextVal = !autoTriageEnabled;
    try {
      await setAiTriageConfig(nextVal);
      setAutoTriageEnabled(nextVal);
      setTriageFeedback(`Autonomous AI Triage on intake is now ${nextVal ? "ENABLED" : "DISABLED"}.`);
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Failed to update configuration");
    }
  }, [autoTriageEnabled]);

  const onConfirmHandover = useCallback(async (id: string, planId?: string) => {
    setBusyId(id);
    try {
      await confirmHandover({ request_id: id, plan_id: planId });
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Handover confirmation failed");
    } finally {
      setBusyId(null);
    }
  }, [refresh]);

  const onConfirmReceipt = useCallback(async (id: string, planId?: string) => {
    setBusyId(id);
    try {
      await confirmReceipt({ request_id: id, plan_id: planId });
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Receipt confirmation failed");
    } finally {
      setBusyId(null);
    }
  }, [refresh]);

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">PACT Command Center</p>
            <h1 className="mt-1 text-3xl font-bold">Request Hub & Live Map</h1>
            <p className="mt-1 max-w-2xl text-sm text-[#7c6a58]">
              Every request — web, SMS, or Android field app — flows through the autonomous AI-checked pipeline and maps to Chennai in real-time.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {/* Auto-triage toggle */}
            <button
              onClick={onToggleAutoTriage}
              className={`flex items-center gap-2 rounded-xl border px-3 py-1.5 font-semibold transition ${
                autoTriageEnabled
                  ? "border-[#4CAF50]/40 bg-[#E8F5E9] text-[#1B5E20]"
                  : "border-[#e3c9a8] bg-[#FFF2DB] text-[#7c4a12] hover:bg-[#FFE5BF]"
              }`}
              title="Automatically triage all newly incoming requests using AI"
            >
              <span className={`h-2.5 w-2.5 rounded-full ${autoTriageEnabled ? "bg-[#4CAF50] animate-pulse" : "bg-[#a1866f]"}`} />
              AI Full Automation: {autoTriageEnabled ? "ACTIVE" : "PAUSED"}
            </button>

            {/* AI Triage All button */}
            <button
              onClick={onAiTriageAll}
              disabled={isTriagingAll || counts.pending === 0}
              className="flex items-center gap-1.5 rounded-xl bg-[#2b1a0e] px-4 py-2 text-xs font-bold text-[#FFFAF3] shadow-sm transition hover:bg-[#4a3a28] disabled:opacity-40"
              title="Evaluate and process all pending requests using the AI Auto-Triage Agent"
            >
              {isTriagingAll ? "Triaging Pending Requests..." : `AI Auto-Triage All (${counts.pending} Pending)`}
            </button>

            <div className="flex items-center gap-2 text-[#7c6a58]">
              <span className={`h-2 w-2 rounded-full ${error ? "bg-red-500" : "animate-pulse bg-green-500"}`} />
              {error ? "Backend unreachable" : lastUpdated ? `Live · ${lastUpdated.toLocaleTimeString()}` : "Connecting…"}
            </div>
          </div>
        </header>

        {triageFeedback && (
          <div className="flex items-center justify-between rounded-xl border border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3 text-sm text-[#7c4a12] shadow-sm animate-fadeIn">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-[#2b1a0e]">[AI Coordination Engine]</span>
              <span>{triageFeedback}</span>
            </div>
            <button
              onClick={() => setTriageFeedback(null)}
              className="text-xs font-bold text-[#7c4a12] hover:text-[#2b1a0e]"
            >
              Dismiss
            </button>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach the FastAPI backend ({error}). Start it with <code>uvicorn app.main:app --reload --host 0.0.0.0</code>.
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

        <div className="grid gap-6 lg:grid-cols-[1fr_500px]">
          <div className="space-y-6">
            <RequestTable
              requests={visible}
              busyId={busyId}
              onAccept={onAccept}
              onReject={onReject}
              onAiTriage={onAiTriage}
              onConfirmHandover={onConfirmHandover}
              onConfirmReceipt={onConfirmReceipt}
            />

            <aside className="h-fit rounded-xl border border-[#FFE5BF] bg-white">
              <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
                <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">Agent Activity Feed</h2>
              </div>
              <ul className="max-h-[300px] space-y-3 overflow-y-auto px-4 py-4">
                {activity.length === 0 && <li className="text-sm text-[#a1866f]">No agent activity yet.</li>}
                {activity.map((a, i) => (
                  <li key={`${a.ts}-${i}`} className="text-xs leading-relaxed">
                    <div className="font-mono text-[10px] text-[#a1866f]">{new Date(a.ts).toLocaleTimeString()}</div>
                    <div>
                      <span className="font-semibold text-[#F62440]">{a.agent}</span>{" "}
                      <span className="text-[#4a3a28]">{a.message}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </aside>
          </div>

          <div className="hidden lg:block h-[85vh] sticky top-8">
            <ChennaiMap requests={requests} />
          </div>
        </div>
      </div>
    </main>
  );
}