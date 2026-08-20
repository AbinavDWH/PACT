"use client";

// The top-bar "every incoming request" view. Same socket, tabular projection.

import { useEffect, useState } from "react";
import { useAgents } from "../../_lib/AgentSocketProvider";
import { authFetch } from "../../_lib/useAgentSocket";
import ConsoleNav from "../ConsoleNav";
import "../admin.css";

interface ArchivedTrace {
  trace_id: string;
  ts?: string;
  completed?: boolean;
}

/** Short local timestamp, or an em dash. Kept out of the row so an unparseable
 *  value cannot throw mid-render. */
function fmt(ts?: string): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString(undefined, {
        month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
}

export default function RequestsPage() {
  const { orderedRuns, connected, eventCount } = useAgents();

  // The socket only carries what arrived since this tab opened, so a fresh load
  // showed an empty table while the database held thirty traces. "All requests"
  // has to mean all of them, not all of this session's.
  const [history, setHistory] = useState<ArchivedTrace[]>([]);
  // Loading and failure were both indistinguishable from "no requests": the
  // empty state claimed nothing had arrived while the fetch was still open.
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    void authFetch("/api/v1/admin/requests?limit=200")
      .then((r) => r.json())
      .then((j) => { if (alive) setHistory((j.traces ?? []) as ArchivedTrace[]); })
      .catch(() => { if (alive) setFailed(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  // Live runs win on conflict: they carry the full reduced state, whereas a
  // persisted row is only a summary.
  const liveIds = new Set(orderedRuns.map((r) => r.traceId));
  const archived = history.filter((h) => !liveIds.has(h.trace_id));
  const total = orderedRuns.length + archived.length;

  return (
    <div className="admin">
      <ConsoleNav connected={connected} eventCount={eventCount} />

      <section className="sectionIntro">
        <h1 className="controlTitle">Everything received so far</h1>
        <p className="controlHint">
          Both transports, both populations, live and archived. Rows marked
          <em> from transcript</em> were replayed from the database rather than
          this session&rsquo;s socket &mdash; the console is not the only place
          a run is recorded.
        </p>
      </section>

      <h2 className="sectionTitle">
        Every request received <span className="sectionCount">{total}</span>
      </h2>

      {loading ? (
        <div className="empty">
          <h2>Loading…</h2>
          <p>Reading the persisted transcript.</p>
        </div>
      ) : failed ? (
        <div className="empty">
          <h2>Could not load the archive</h2>
          <p>
            The live stream below is unaffected; only the persisted history
            failed to load. Check the backend, then reload.
          </p>
        </div>
      ) : total === 0 ? (
        <div className="empty">
          <h2>Nothing yet</h2>
          <p>Requests appear here the moment they arrive, matched or not.</p>
        </div>
      ) : (
        /* The scroll container is the fix that matters here: six columns of
           trace ids and allocation lists overflowed the viewport and scrolled
           the whole page sideways on anything narrow. */
        <div className="tableScroll">
          <table className="reqTable">
            <caption className="srOnly">
              Every request received, live runs first, then archived traces read
              back from the persisted transcript.
            </caption>
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Received</th>
                <th scope="col">Summary</th>
                <th scope="col">Status</th>
                <th scope="col">Agents</th>
                <th scope="col">Decision</th>
                <th scope="col">Allocated</th>
              </tr>
            </thead>
            <tbody>
              {orderedRuns.map((r) => (
                <tr key={r.traceId}>
                  <th scope="row" className="trace">{r.traceId}</th>
                  <td className="dimCell nowrap">{fmt(r.startedAt)}</td>
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
                  <th scope="row" className="trace">{h.trace_id}</th>
                  <td className="dimCell nowrap">{fmt(h.ts)}</td>
                  <td className="dimCell">—</td>
                  <td>
                    <span className={`badge ${h.completed ? "committed" : "incomplete"}`}>
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
