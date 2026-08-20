"use client";

// Map section.
//
// The same MapPanel the deliberation card embeds, lifted to a section of its
// own and pointed at whichever run you select. A juror asking "where is this
// actually happening?" should not have to scroll into a card to find out.

import { useEffect, useMemo, useState } from "react";
import { useAgents } from "../../_lib/AgentSocketProvider";
import MapPanel, { pointsFromRun } from "../../_components/MapPanel";
import ConsoleNav from "../ConsoleNav";
import "../admin.css";
import "./map.css";

export default function MapSection() {
  const { orderedRuns, connected, eventCount } = useAgents();
  const [selected, setSelected] = useState<string | null>(null);

  // Follow the newest run until a juror picks one deliberately; then stay put
  // so the map does not jump out from under them mid-explanation.
  const [pinned, setPinned] = useState(false);
  useEffect(() => {
    if (!pinned && orderedRuns.length) setSelected(orderedRuns[0].traceId);
  }, [orderedRuns, pinned]);

  const run = useMemo(
    () => orderedRuns.find((r) => r.traceId === selected) ?? orderedRuns[0],
    [orderedRuns, selected],
  );
  const points = useMemo(() => (run ? pointsFromRun(run) : []), [run]);

  const requester = points.find((p) => p.kind === "request");
  const candidates = points.filter((p) => p.kind !== "request");

  return (
    <div className="admin">
      <ConsoleNav connected={connected} eventCount={eventCount} />

      <section className="sectionIntro">
        <h1 className="controlTitle">Where the request is</h1>
        <p className="controlHint">
          The red point is the person asking for help. The blue points are the
          helpers a geospatial query found nearby — the same query whose result
          the agents argue over. Tiles are cached locally, so this map still
          draws with no internet.
        </p>
      </section>

      {orderedRuns.length === 0 ? (
        <div className="empty">
          <h2>No requests to place yet</h2>
          <p>
            Send one from the <strong>Deliberation</strong> section and it will
            appear here.
          </p>
        </div>
      ) : (
        <div className="mapLayout">
          <div className="mapSide">
            <h2 className="sectionTitle">Requests</h2>
            <ul className="mapList">
              {orderedRuns.slice(0, 12).map((r) => (
                <li key={r.traceId}>
                  <button
                    className={`mapListItem ${r.traceId === run?.traceId ? "active" : ""}`}
                    onClick={() => {
                      setSelected(r.traceId);
                      setPinned(true);
                    }}
                  >
                    <span className="trace">{r.traceId}</span>
                    <span className="mapListSummary">{r.summary || "—"}</span>
                    <span className={`badge ${r.status}`}>
                      {r.status.replace(/_/g, " ")}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="mapMain">
            {points.length === 0 ? (
              <div className="empty">
                <h2>No position on this request</h2>
                <p>
                  It arrived without coordinates, or the geospatial query
                  returned nothing in range.
                </p>
              </div>
            ) : (
              <>
                <MapPanel points={points} height={520} />
                <div className="mapFacts">
                  <div className="mapFact">
                    <span className="mapFactK">{candidates.length}</span>
                    <span className="mapFactL">helpers found nearby</span>
                  </div>
                  {requester && (
                    <div className="mapFact">
                      <span className="mapFactK mono">
                        {requester.lat.toFixed(3)}, {requester.lon.toFixed(3)}
                      </span>
                      <span className="mapFactL">requester position</span>
                    </div>
                  )}
                  {/* Three states, not two. The backend reports `geo_live` on
                      `run.completed` and nowhere else, so it is undefined for
                      the whole of a live run -- and reading undefined as false
                      told a juror the run was on fixtures while $geoNear had
                      in fact just returned rows. */}
                  <div className="mapFact">
                    <span className={`mapFactK ${run?.geoLive === false ? "warnText" : ""}`}>
                      {run?.geoLive === true
                        ? "live query"
                        : run?.geoLive === false
                          ? "fixtures"
                          : "pending"}
                    </span>
                    <span className="mapFactL">
                      {run?.geoLive === true
                        ? "candidates came from the database"
                        : run?.geoLive === false
                          ? "database returned nothing in range"
                          : "reported when the run completes"}
                    </span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
