"use client";

// The top-bar "every incoming request" view. Same socket, tabular projection.

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAgents } from "../../_lib/AgentSocketProvider";
import { authFetch } from "../../_lib/useAgentSocket";
import "../admin.css";

export default function RequestsPage() {
  const { orderedRuns, connected, eventCount } = useAgents();

  // The socket only carries what arrived since this tab opened, so a fresh load
  // showed an empty table while the database held thirty traces. "All requests"
  // has to mean all of them, not all of this session's.
  const [history, setHistory] = useState<
    { trace_id: string; ts?: string; completed?: boolean }[]
  >([]);
  useEffect(() => {
    let alive = true;
    void authFetch("/api/v1/admin/requests?limit=200")
      .then((r) => r.json())
      .then((j) => { if (alive) setHistory(j.traces ?? []); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // Live runs win on conflict: they carry the full reduced state, whereas a
  // persisted row is only a summary.
  const liveIds = new Set(orderedRuns.map((r) => r.traceId));
  const archived = history.filter((h) => !liveIds.has(h.trace_id));
  const total = orderedRuns.length + archived.length;

  return (
    <div className="admin">
      <header className="topbar">
        <div className="brand">
          <span className="mark">PACT</span>
          <span className="sub">Admin Portal</span>
        </div>
        <nav className="nav">
          <Link className="navItem" href="/admin">Live Matches</Link>
          <span className="navItem active">All Requests</span>
        </nav>
        <div className="status">
          <span className={`dot ${connected ? "on" : "off"}`} />
          {connected ? "connected" : "reconnecting"}
          <span className="count">{eventCount} events</span>
        </div>
      </header>

      <h2 className="sectionTitle">Every request received ({total})</h2>

      {total === 0 ? (
        <div className="empty">
          <h2>Nothing yet</h2>
          <p>Requests appear here the moment they arrive, matched or not.</p>
        </div>
      ) : (
        <div className="stream">
          <table className="reqTable">
            <thead>
              <tr>
                <th>Request</th><th>Summary</th><th>Status</th>
                <th>Agents</th><th>Decision</th><th>Allocated</th>
              </tr>
            </thead>
            <tbody>
              {orderedRuns.map((r) => (
                <tr key={r.traceId}>
                  <td className="trace">{r.traceId}</td>
                  <td>{r.summary || "—"}</td>
                  <td><span className={`badge ${r.status}`}>{r.status.replace("_", " ")}</span></td>
                  <td className="dimCell">{r.agentsSeen.length}</td>
                  <td className="dimCell">
                    {r.adminAction
                      ? `${r.adminAction.action}${r.adminAction.option_id ? ` → ${r.adminAction.option_id}` : ""}`
                      : r.status === "awaiting_admin" ? "pending" : "—"}
                  </td>
                  <td className="dimCell">
                    {r.committed
                      ? r.committed.allocations.map((a) => `${a.qty} × ${a.name}`).join(", ")
                      : "—"}
                  </td>
                </tr>
              ))}
              {archived.map((h) => (
                <tr key={h.trace_id}>
                  <td className="trace">{h.trace_id}</td>
                  <td className="dimCell">
                    {h.ts ? new Date(h.ts).toLocaleString() : "—"}
                  </td>
                  <td>
                    <span className={`badge ${h.completed ? "committed" : ""}`}>
                      {h.completed ? "completed" : "incomplete"}
                    </span>
                  </td>
                  <td className="dimCell">—</td>
                  <td className="dimCell">—</td>
                  <td className="dimCell">from transcript</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
