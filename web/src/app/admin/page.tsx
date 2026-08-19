"use client";

// Admin portal: live match stream (primary view).
// Every panel here is driven by the WebSocket event schema in agents.md 3.2,
// so replacing the scripted pipeline with real Groq agents changes nothing.

import { useState } from "react";
import Link from "next/link";
import { useAgents } from "../_lib/AgentSocketProvider";
import { DETERMINISTIC, type DebateTurn, type Run } from "../_lib/types";
import { SmsSimulator } from "./SmsSimulator";
import MapPanel, { pointsFromRun } from "../_components/MapPanel";
import "./admin.css";

const NEEDS = ["medical_kits", "water_kits", "food_kits", "tents", "rescue_team"];

export default function AdminPage() {
  const { orderedRuns, connected, eventCount, decide, simulate } = useAgents();
  const [need, setNeed] = useState(NEEDS[0]);
  const [qty, setQty] = useState(3);
  const [busy, setBusy] = useState(false);

  const fire = async () => {
    setBusy(true);
    await simulate({ need, quantity: qty, location_name: "Region A", urgency: "critical" });
    setTimeout(() => setBusy(false), 600);
  };

  const live = orderedRuns.filter((r) => r.status === "running" || r.status === "awaiting_admin");
  const done = orderedRuns.filter((r) => r.status === "committed" || r.status === "rejected");

  return (
    <div className="admin">
      <header className="topbar">
        <div className="brand">
          <span className="mark">PACT</span>
          <span className="sub">Admin Portal</span>
        </div>
        <nav className="nav">
          <span className="navItem active">Live Matches</span>
          <Link className="navItem" href="/admin/requests">All Requests</Link>
        </nav>
        <div className="status">
          <span className={`dot ${connected ? "on" : "off"}`} />
          {connected ? "connected" : "reconnecting"}
          <span className="count">{eventCount} events</span>
        </div>
      </header>

      <section className="control">
        <label>
          Need
          <select value={need} onChange={(e) => setNeed(e.target.value)}>
            {NEEDS.map((n) => <option key={n} value={n}>{n.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        <label>
          Quantity
          <input type="number" min={1} value={qty}
                 onChange={(e) => setQty(Math.max(1, Number(e.target.value)))} />
        </label>
        <button onClick={fire} disabled={busy || !connected}>
          {busy ? "Dispatching…" : "Simulate incoming request"}
        </button>
        <p className="hint">
          Scripted pipeline — real Groq agents drop in behind this same event stream.
        </p>
      </section>

      <SmsSimulator />

      {orderedRuns.length === 0 && (
        <div className="empty">
          <h2>No requests yet</h2>
          <p>Fire a simulated request above to watch the agents deliberate.</p>
        </div>
      )}

      {live.length > 0 && <h2 className="sectionTitle">Live</h2>}
      <div className="stream">
        {live.map((r) => <RunCard key={r.traceId} run={r} decide={decide} />)}
      </div>

      {done.length > 0 && <h2 className="sectionTitle">Completed</h2>}
      <div className="stream">
        {done.map((r) => <RunCard key={r.traceId} run={r} decide={decide} />)}
      </div>
    </div>
  );
}

function RunCard({ run, decide }: {
  run: Run;
  decide: (id: string, a: "approve" | "override" | "reject", o?: string) => void;
}) {
  const waiting = run.status === "awaiting_admin" && run.decisionId;

  return (
    <article className={`card ${run.status}`}>
      <div className="cardHead">
        <div>
          <span className="trace">{run.traceId}</span>
          <span className={`badge ${run.status}`}>{run.status.replace("_", " ")}</span>
        </div>
        <span className="summary">{run.summary}</span>
      </div>

      <div className="agentRail">
        {run.agentsSeen.map((a) => (
          <span key={a} className={`chip ${DETERMINISTIC.includes(a) ? "det" : "llm"}`}>
            {a.replace(/^a\d+_/, "")}
          </span>
        ))}
      </div>

      <div className="bubbles">
        {run.bubbles.map((b) => (
          <div key={b.key} className={`bubble ${DETERMINISTIC.includes(b.agent) ? "det" : "llm"}`}>
            <span className="who">{b.label}</span>
            {b.toolCall ? (
              <code className="tool">
                {b.toolCall.tool}({JSON.stringify(b.toolCall.args)}) → {b.toolCall.result_count} rows
                <span className="ms"> {b.toolCall.ms}ms</span>
              </code>
            ) : (
              <p>
                {b.text}
                {b.streaming && <span className="caret" />}
                {typeof b.confidence === "number" && (
                  <span className="conf">conf {b.confidence.toFixed(2)}</span>
                )}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Crisis point, the candidates $geoNear returned, and lines to whoever
          was actually committed (memory_draft.md 13). Only rendered once
          something has a position, so an unlocated request does not show an
          empty map claiming otherwise. */}
      {(run.requestPoint || (run.candidates?.length ?? 0) > 0) && (
        <MapPanel points={pointsFromRun(run)} height={280} />
      )}

      {run.turns.length > 0 && <Debate turns={run.turns} winner={run.debateWinner}
                                       dissent={run.debateDissent} />}

      {run.options.length > 0 && (
        <div className="options">
          {run.options.map((o) => (
            <div key={o.option_id}
                 className={`option ${o.option_id === run.chosenOptionId ? "chosen" : ""}`}>
              <span className="optLabel">{o.label.replace(/_/g, " ")}</span>
              <span className="optMeta">{o.coverage_pct}% covered · {o.total_eta} min</span>
              <ul>
                {o.allocations.map((a, i) => (
                  <li key={i}>{a.qty} × {a.resource.replace(/_/g, " ")} — {a.name}</li>
                ))}
              </ul>
              {o.option_id === run.chosenOptionId && <span className="pick">arbiter&rsquo;s choice</span>}
            </div>
          ))}
        </div>
      )}

      {waiting && (
        <div className="gate">
          <div className="gateMsg">
            <strong>Awaiting decision</strong>
            {run.justification && <em>{run.justification}</em>}
            {run.autopilot && <span className="auto">autopilot approves in {run.gateTimeoutS}s</span>}
          </div>
          <div className="gateActions">
            <button className="approve" onClick={() => decide(run.decisionId!, "approve")}>
              Approve
            </button>
            {run.options.filter((o) => o.option_id !== run.chosenOptionId).map((o) => (
              <button key={o.option_id} className="override"
                      onClick={() => decide(run.decisionId!, "override", o.option_id)}>
                Override → {o.label.replace(/_/g, " ")}
              </button>
            ))}
            <button className="reject" onClick={() => decide(run.decisionId!, "reject")}>
              Reject
            </button>
          </div>
        </div>
      )}

      {run.adminAction && (
        <div className="adminNote">
          {run.adminAction.action === "auto_approve"
            ? "Auto-approved by autopilot."
            : `Admin ${run.adminAction.action}`}
          {run.adminAction.option_id ? ` → ${run.adminAction.option_id}` : ""}
        </div>
      )}

      {run.privacy && (
        <div className="privacy">
          <div className="privacyHead">
            <span className="pTitle">Privacy boundary</span>
            {/* The measured count. A fixed list looks identical whether the
                redactor ran or not; this number comes off the real payload. */}
            <span className="pCount">
              {run.privacy.fieldsRedacted} field instances redacted
            </span>
          </div>

          <div><span className="pLabel shared">shared</span> {run.privacy.shared.join(", ")}</div>
          <div><span className="pLabel masked">masked</span> {run.privacy.masked.join(", ")}</div>
          <div><span className="pLabel held">withheld</span> {run.privacy.withheld.join(", ")}</div>

          {Object.keys(run.privacy.byField).length > 0 && (
            <div className="pByField">
              {Object.entries(run.privacy.byField).map(([f, n]) => (
                <span key={f} className="pChip">{f.replace(/_/g, " ")} ×{n}</span>
              ))}
            </div>
          )}

          {run.privacy.orgBlockedTypes.length > 0 && (
            <div className="pOrg">
              Organizations additionally never receive{" "}
              {run.privacy.orgBlockedTypes.length} event types, including the
              cross-organization debate.
            </div>
          )}
        </div>
      )}

      {/* Revelation is a state transition, not a default. Nothing else in the
          system flips it: only a helper accepting. */}
      {run.reveals.map((r, i) => (
        <div key={i} className="reveal">
          <span className="revealBadge">unlocked</span>
          <span>
            {r.fields.map((f) => f.replace(/_/g, " ")).join(", ")} released to{" "}
            <strong>{r.to}</strong>
            {r.audienceBefore && r.audienceAfter
              ? ` — ${r.audienceBefore} → ${r.audienceAfter}`
              : ""}
          </span>
        </div>
      ))}

      {run.committed && (
        <div className="committed">
          <strong>{run.committed.match_id}</strong>
          <ul>
            {run.committed.allocations.map((a, i) => (
              <li key={i}>{a.qty} × {a.resource.replace(/_/g, " ")} — {a.name} · ETA {a.eta_min} min</li>
            ))}
          </ul>
          {run.committed.unmet > 0 && <span className="unmet">{run.committed.unmet} unmet</span>}
        </div>
      )}

      {/* The two dispatch paths differ in behaviour, not wording: an org
          allocation is not acceptable until its portal names a helper. */}
      {run.notifications.map((n, i) => (
        <div key={i} className="notify">
          <div className="notifyHead">
            <span className={`routeChip ${n.route ?? ""}`}>
              {n.route === "org_portal" ? "org portal"
                : n.route === "direct_volunteer" ? "direct to volunteer"
                : n.channel}
            </span>
            {n.state && (
              <span className={`stateChip ${n.acceptableNow ? "ready" : "waiting"}`}>
                {n.state.replace(/_/g, " ")}
              </span>
            )}
            <span className="notifyTarget">{n.target_masked}</span>
          </div>
          <div className="notifyMsg">{n.message}</div>
          {n.detail && <div className="notifyDetail">{n.detail}</div>}
        </div>
      ))}

      {/* geo_live false means the run used fixtures. The pipeline continues
          either way, so this is the only place it becomes visible. */}
      {run.geoLive === false && (
        <div className="geoWarn">
          <strong>$geoNear returned nothing</strong> — this run used hardcoded
          fixtures, not the database. Reseed near the request location:
          <code>POST /api/v1/admin/seed {"{"}lat, lon{"}"}</code>
        </div>
      )}

      {run.errors.map((e, i) => (
        <div key={i} className="err">
          {e.agent} {e.code}{e.fallback_used ? " — deterministic fallback used" : ""}
        </div>
      ))}
    </article>
  );
}

function Debate({ turns, winner, dissent }: {
  turns: DebateTurn[]; winner?: string; dissent?: string;
}) {
  return (
    <div className="debate">
      <span className="debateTitle">Deliberation</span>
      {turns.map((t) => (
        <div key={`${t.debate_id}-${t.turn_no}`}
             className={`turn ${t.stance} ${t.rebuts ? "reply" : ""}`}>
          <span className="speaker">{t.speaker}</span>
          <span className="claim">{t.claim}</span>
          {t.rebuts && <span className="rebuts">rebuts {t.rebuts}</span>}
        </div>
      ))}
      {winner && (
        <div className="verdict">
          resolved → <strong>{winner}</strong>
          {dissent && <em>dissent: {dissent}</em>}
        </div>
      )}
    </div>
  );
}
