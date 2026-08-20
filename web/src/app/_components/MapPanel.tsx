"use client";

// The portal map (memory_draft.md 13): crisis points, helper positions and
// allocation lines.
//
// Tiles come from OUR backend, not from an upstream CDN. The backend caches
// every tile on disk, so once prefetched the map renders with no internet at
// all -- which is the honest meaning of "offline OpenStreetMap tiles,
// pre-cached" (memory_draft.md 15). Pointing straight at tile.openstreetmap.org
// would look identical here and stop working the moment the venue wifi did,
// which is the one condition this project assumes.
//
// Positions rendered here are whatever the event stream carried. The admin
// audience sees exact coordinates by policy; every other audience is redacted
// server-side before it reaches any client, so there is nothing to mask again
// in this component.

// maplibre-gl 6 removed the default export; the namespace import is the
// supported form.
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { API_BASE } from "../_lib/useAgentSocket";
import type { Run } from "../_lib/types";

export interface MapPoint {
  lat: number;
  lon: number;
  kind: "request" | "candidate" | "allocated";
  label: string;
  detail?: string;
}

const COLOURS: Record<MapPoint["kind"], string> = {
  request: "#ff6b6b",     // the person asking
  candidate: "#7aa2f7",   // considered by $geoNear
  allocated: "#4ec9a8",   // actually committed to
};

/** A style with one raster source, served by us. No external hosts at all:
 *  a style referencing a CDN would fail closed on an offline machine. */
function offlineStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: [`${API_BASE}/api/v1/tiles/{z}/{x}/{y}.png`],
        tileSize: 256,
        // Required by OSM's licence wherever their data is shown.
        attribution: "© OpenStreetMap contributors · cached locally by PACT",
      },
    },
    layers: [
      // Drawn under the tiles so a missing (transparent) tile shows this
      // instead of the page background, keeping the map legible offline.
      { id: "bg", type: "background", paint: { "background-color": "#0d1117" } },
      { id: "osm", type: "raster", source: "osm",
        paint: { "raster-opacity": 0.85 } },
    ],
  };
}

export function pointsFromRun(run: Run): MapPoint[] {
  const pts: MapPoint[] = [];

  const req = run.requestPoint;
  if (req) {
    pts.push({
      lat: req.lat, lon: req.lon, kind: "request",
      label: run.traceId,
      detail: run.summary || "incoming request",
    });
  }

  const allocatedIds = new Set(
    (run.committed?.allocations ?? []).map((a) => a.cand_id).filter(Boolean),
  );

  for (const c of run.candidates ?? []) {
    if (c.lat == null || c.lon == null) continue;
    const committed = allocatedIds.has(c.cand_id);
    pts.push({
      lat: c.lat, lon: c.lon,
      kind: committed ? "allocated" : "candidate",
      label: c.name,
      detail: `${c.distance_km} km · ETA ${c.eta_minutes} min`,
    });
  }
  return pts;
}

export default function MapPanel({ points, height = 320 }: {
  points: MapPoint[];
  height?: number;
}) {
  const container = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);

  // Create once. Re-creating on every render would restart every tile fetch.
  useEffect(() => {
    if (!container.current || map.current) return;
    map.current = new maplibregl.Map({
      container: container.current,
      style: offlineStyle(),
      center: [80.006, 13.008],      // [lng, lat] -- always in that order
      zoom: 11,
      attributionControl: { compact: true },
    });
    map.current.addControl(new maplibregl.NavigationControl({ showCompass: false }),
                           "top-right");

    // MapLibre sizes its WebGL canvas once, at construction. Inside a run card
    // the container is already at its final width by then; on the map section
    // the CSS grid resolves after mount, so the canvas stayed at its initial
    // width and painted tiles across only part of a much wider box -- the
    // controls and attribution moved with the container, the map did not.
    const ro = new ResizeObserver(() => map.current?.resize());
    ro.observe(container.current);

    return () => {
      ro.disconnect();
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Redraw markers and the allocation lines whenever the points change.
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const draw = () => {
      markers.current.forEach((mk) => mk.remove());
      markers.current = [];
      if (!points.length) return;

      for (const p of points) {
        const el = document.createElement("div");
        el.className = `mapPin ${p.kind}`;
        el.style.background = COLOURS[p.kind];
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([p.lon, p.lat])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(
            `<strong>${escapeHtml(p.label)}</strong>` +
            (p.detail ? `<br/>${escapeHtml(p.detail)}` : ""),
          ))
          .addTo(m);
        markers.current.push(marker);
      }

      // Lines from the request to each committed helper: the allocation, drawn.
      const request = points.find((p) => p.kind === "request");
      const allocated = points.filter((p) => p.kind === "allocated");
      // Typed structurally rather than via the GeoJSON namespace, which needs
      // @types/geojson -- one dependency for one shape.
      const fc = {
        type: "FeatureCollection" as const,
        features: request
          ? allocated.map((a) => ({
              type: "Feature" as const,
              properties: {},
              geometry: {
                type: "LineString" as const,
                coordinates: [[request.lon, request.lat], [a.lon, a.lat]],
              },
            }))
          : [],
      };

      const src = m.getSource("alloc") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(fc);
      } else {
        m.addSource("alloc", { type: "geojson", data: fc });
        m.addLayer({
          id: "alloc", type: "line", source: "alloc",
          paint: { "line-color": COLOURS.allocated, "line-width": 2,
                   "line-dasharray": [2, 1.5] },
        });
      }

      const bounds = new maplibregl.LngLatBounds();
      points.forEach((p) => bounds.extend([p.lon, p.lat]));
      // A single point yields a zero-area bounds, which fitBounds cannot use.
      if (points.length === 1) {
        m.easeTo({ center: [points[0].lon, points[0].lat], zoom: 13 });
      } else {
        m.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 400 });
      }
    };

    if (m.isStyleLoaded()) draw();
    else m.once("load", draw);
  }, [points]);

  const kinds = new Set(points.map((p) => p.kind));

  return (
    <div className="mapBlock">
      <div className="mapWrap" style={{ height }}>
        <div ref={container} className="mapCanvas" />
        {points.length === 0 && (
          <div className="mapEmpty">No positioned events yet</div>
        )}
      </div>
      {/* Three marker colours had no key at all, which made the map rely on
          colour alone to say which pin is the seeker and which was actually
          committed. Only the kinds present are listed, so it does not promise
          an "allocated" pin before one exists. */}
      {points.length > 0 && (
        <div className="mapLegend">
          {LEGEND.filter(([kind]) => kinds.has(kind)).map(([kind, label]) => (
            <span key={kind}>
              <i style={{ background: COLOURS[kind] }} aria-hidden="true" />
              {label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const LEGEND: [MapPoint["kind"], string][] = [
  ["request", "requester"],
  ["candidate", "candidate from $geoNear"],
  ["allocated", "committed allocation"],
];

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}
