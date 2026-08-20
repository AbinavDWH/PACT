"use client";

// Admin console: live deliberation stream (primary view).
//
// Every panel is driven by the WebSocket event schema in agents.md 3.2. The
// agents behind it are the live Groq ones -- the backend module is still named
// `scripted.py` for history, but it calls the real model and the real
// `$geoNear`. This page used to claim otherwise in a caption; the mode chip in
// the control bar now reports what the backend actually says it is running.

import { useMemo, useState } from "react";
import { useAgents } from "../_lib/AgentSocketProvider";
import { useConsoleMeta } from "../_lib/useConsoleMeta";
import { DETERMINISTIC, type DebateTurn, type Run } from "../_lib/types";
import { CodecConsole } from "./CodecConsole";
import ConsoleNav from "./ConsoleNav";
import MapPanel, { pointsFromRun } from "../_components/MapPanel";
import "./admin.css";

/** One-click stories for the jury.
 *
 *  A juror who has to choose a resource, a quantity and a pair of coordinates
 *  before anything happens will not press the button. Each of these is a whole
 *  scenario, and each is chosen to make the pipeline behave differently against
 *  the seeded stock rather than to look varied:
 *
 *    - rescue_team: 4 exist in the entire seed, so 3 is genuine scarcity and
 *      the advocates actually argue;
 *    - water_kits: held by three separate owners, so the solver has to split
 *      one request across providers;
 *    - tents: 120 seeded against a request for 150, so the run commits with a
 *      reported shortfall instead of inventing stock.
 *
 *  `dLat`/`dLon` nudge the request off the seeded centre by a few km so the
 *  three do not land on the same pin, while staying well inside the first rung
 *  of the radius ladder.
 */
const SCENARIOS = [
  {
    id: "collapse",
    title: "Building collapse",
    detail: "3 rescue teams · 4 exist anywhere",
    need: "rescue_team",
    quantity: 3,
    dLat: 0,
    dLon: 0,
  },
  {
    id: "flood",
    title: "Flood cuts off a ward",
    detail: "200 water kits · no single provider has them",
    need: "water_kits",
    quantity: 200,
    dLat: 0.045,
    dLon: -0.03,
  },
  {
    id: "shelter",
    title: "Cyclone shelter opening",
    detail: "150 tents · only 120 seeded, so demand goes unmet",
    need: "tents",
    quantity: 150,
    dLat: -0.038,
    dLon: 0.05,
  },
] as const;

export default function AdminPage() {
  const { orderedRuns, connected, eventCount, decide, dispatch } = useAgents();
  const meta = useConsoleMeta();

  // null means "the operator has not chosen yet", so the field falls through to
  // whatever the backend reports. Held as null rather than synced into state by
  // an effect: copying fetched values into state on arrival is a cascading
  // render, and it also races the fetch on first paint.
  const [needChoice, setNeedChoice] = useState<string | null>(null);
  const [qty, setQty] = useState(3);
  const [latInput, setLatInput] = useState<string | null>(null);
  const [lonInput, setLonInput] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preset, setPreset] = useState<string | null>(null);

  const need = needChoice ?? meta.inventory[0]?.resource ?? "";
  const lat = latInput ?? (meta.anchor ? String(meta.anchor.lat) : "");
  const lon = lonInput ?? (meta.anchor ? String(meta.anchor.lon) : "");

  const latNum = Number(lat);
  const lonNum = Number(lon);
  const coordsValid =
    lat.trim() !== "" && lon.trim() !== "" &&
    Number.isFinite(latNum) && Number.isFinite(lonNum) &&
    Math.abs(latNum) <= 90 && Math.abs(lonNum) <= 180;

  const canFire = connected && !busy && need !== "" && coordsValid;

  const fire = async () => {
    if (!canFire) return;
    setBusy(true);
    try {
      await dispatch({
        need,
        quantity: qty,
        urgency: "critical",
        lat: latNum,
        lon: lonNum,
      });
    } finally {
      // Held briefly so the button reads as having done something even when the
      // POST returns before the first event arrives.
      setTimeout(() => setBusy(false), 500);
    }
  };

  /** Fire a whole scenario. Deliberately does not write the manual inputs:
   *  a preset that silently rewrote the four fields would leave the operator
   *  unsure what they were about to send next. */
  const runScenario = async (s: (typeof SCENARIOS)[number]) => {
    if (!meta.anchor || busy) return;
    setBusy(true);
    setPreset(s.id);
    try {
      await dispatch({
        need: s.need,
        quantity: s.quantity,
        urgency: "critical",
        lat: meta.anchor.lat + s.dLat,
        lon: meta.anchor.lon + s.dLon,
      });
    } finally {
      setTimeout(() => { setBusy(false); setPreset(null); }, 500);
    }
  };

  /** A scenario whose resource is not seeded would dispatch into an empty
   *  match set and look like a failure, so it is disabled and says why. */
  const stockFor = (need: string) =>
    meta.inventory.find((r) => r.resource === need)?.available ?? 0;

  const atAnchor =
    meta.anchor != null &&
    Math.abs(latNum - meta.anchor.lat) < 1e-6 &&
    Math.abs(lonNum - meta.anchor.lon) < 1e-6;

  const live = useMemo(
    () => orderedRuns.filter((r) => r.status === "running" || r.status === "awaiting_admin"),
    [orderedRuns],
  );
  const done = useMemo(
    // A failed run belongs here too. Left out, it stayed in "Live" forever
    // and read as still deliberating.
    () => orderedRuns.filter((r) => r.status === "committed" ||
                                    r.status === "rejected" ||
                                    r.status === "unmet" ||
                                    r.status === "failed"),
    [orderedRuns],
  );

  return (
    <div className="admin">
      <ConsoleNav connected={connected} eventCount={eventCount} />

      <section className="control" aria-label="Inject a request">
        <div className="controlIntro">
          <h1 className="controlTitle">Dispatch a request</h1>
          <p className="controlHint">
            Stands in for a request arriving from the app. The agents below
            handle it exactly as they would a real one.
          </p>
        </div>

        <div className="scenarios">
          {SCENARIOS.map((s) => {
            const stock = stockFor(s.need);
            const ready = connected && !busy && meta.anchor != null && stock > 0;
            return (
              <button
                key={s.id}
                className={`scenario ${preset === s.id ? "running" : ""}`}
                onClick={() => void runScenario(s)}
                disabled={!ready}
                title={
                  meta.anchor == null
                    ? "Seed the fixtures first"
                    : stock === 0
                      ? `No ${s.need.replace(/_/g, " ")} seeded`
                      : s.detail
                }
              >
                {preset === s.id && <span className="spinner" aria-hidden="true" />}
                <span className="scenarioTitle">{s.title}</span>
                <span className="scenarioDetail">
                  {stock === 0 ? "not seeded" : s.detail}
                </span>
              </button>
            );
          })}
        </div>

        <p className="controlOr">Or build one by hand</p>

        <label>
          Need
          <select value={need} onChange={(e) => setNeedChoice(e.target.value)}
                  disabled={meta.inventory.length === 0}>
            {meta.inventory.length === 0 && (
              <option value="">{meta.loading ? "loading…" : "no stock"}</option>
            )}
            {/* Real resources, with the real available quantity beside each --
                so picking one that cannot be filled is a visible choice. */}
            {meta.inventory.map((r) => (
              <option key={r.resource} value={r.resource}>
                {r.resource.replace(/_/g, " ")} ({r.available} avail)
              </option>
            ))}
          </select>
        </label>

        <label>
          Quantity
          <input type="number" min={1} value={qty}
                 onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))} />
        </label>

        {/* The request position. Previously absent entirely, which is what sent
            every admin-injected run down the fixture path. */}
        <label>
          Latitude
          <input className="coord" inputMode="decimal" value={lat}
                 aria-invalid={lat !== "" && !coordsValid}
                 onChange={(e) => setLatInput(e.target.value)} />
        </label>
        <label>
          Longitude
          <input className="coord" inputMode="decimal" value={lon}
                 aria-invalid={lon !== "" && !coordsValid}
                 onChange={(e) => setLonInput(e.target.value)} />
        </label>

        <button className="fire" onClick={fire} disabled={!canFire}>
          {busy && <span className="spinner" aria-hidden="true" />}
          {busy ? "Dispatching…" : "Dispatch request"}
        </button>

        <p className="controlMeta">
          <span className={`modeChip ${meta.liveAgents ? "" : "degraded"}`}>
            {meta.liveAgents ? "live agents" : "deterministic fallback"}
          </span>
          <span className={`modeChip ${meta.mongoConnected ? "" : "degraded"}`}>
            {meta.mongoConnected ? "mongo connected" : "mongo offline"}
          </span>
          {meta.autopilot && (
            <span className="modeChip degraded">
              autopilot{meta.gateTimeoutS != null ? ` ${meta.gateTimeoutS}s` : ""}
            </span>
          )}

          {meta.error ? (
            <>Backend unreachable — check the API address, then <button
              className="linkBtn" onClick={() => void meta.refresh()}>retry</button>.</>
          ) : meta.anchor == null && !meta.loading ? (
            <>No fixtures seeded, so <code>$geoNear</code> has nothing to match
              against. Seed first: <code>POST /api/v1/admin/seed</code></>
          ) : atAnchor ? (
            <>Dispatching at the seeded centre{" "}
              <span className="anchorNote">
                {meta.anchor?.lat}, {meta.anchor?.lon}
              </span>
              {meta.radiusLadderKm.length > 0 &&
                ` — radius ladder ${meta.radiusLadderKm.join("/")} km`}
            </>
          ) : coordsValid && meta.anchor ? (
            <>Off-centre by{" "}
              {haversineKm(latNum, lonNum, meta.anchor.lat, meta.anchor.lon).toFixed(0)} km.{" "}
              <button className="linkBtn" onClick={() => {
                // Back to falling through to the reported anchor.
                setLatInput(null);
                setLonInput(null);
              }}>Reset to seeded centre</button>
            </>
          ) : (
            <>Enter a valid latitude and longitude.</>
          )}
        </p>
      </section>

      <CodecConsole />

      {orderedRuns.length === 0 && (
        <div className="empty">
          <h2>Nothing in flight</h2>
          <p>
            Dispatch a request above, or send a codec string through the
            console, to watch the agents deliberate.
          </p>
        </div>
      )}

      {/* aria-live on the stream: runs arrive on their own and a screen reader
          would otherwise never be told. "polite" rather than "assertive" so it
          does not interrupt on every token. */}
      <div aria-live="polite" aria-relevant="additions">
        {live.length > 0 && (
          <h2 className="sectionTitle">
            Live <span className="sectionCount">{live.length}</span>
          </h2>
        )}
        <div className="stream">
          {live.map((r) => <RunCard key={r.traceId} run={r} decide={decide} />)}
        </div>

        {done.length > 0 && (
          <h2 className="sectionTitle">
            Completed <span className="sectionCount">{done.length}</span>
          </h2>
        )}
        <div className="stream">
          {done.map((r) => <RunCard key={r.traceId} run={r} decide={decide} />)}
        </div>
      </div>
    </div>
  );
}

/** Great-circle distance, to tell the operator how far off the fixtures they
 *  are aiming -- the difference between a real match and a fixture-backed one. */
function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(bLat - aLat);
  const dLon = rad(bLon - aLon);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(aLat)) * Math.cos(rad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
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
          fixtures, not the database. Either the request landed outside the
          seeded area, or nothing is seeded. Reseed near the request location:
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
