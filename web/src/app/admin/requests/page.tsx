"use client";

// The top-bar "every incoming request" view. Same socket, tabular projection.

import Link from "next/link";
import { useAgents } from "../../_lib/AgentSocketProvider";
import "../admin.css";

export default function RequestsPage() {
  const { orderedRuns, connected, eventCount } = useAgents();

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

      <h2 className="sectionTitle">Every request received ({orderedRuns.length})</h2>

      {orderedRuns.length === 0 ? (
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
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
