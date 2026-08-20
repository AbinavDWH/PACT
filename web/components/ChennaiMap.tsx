"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Tooltip, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { listLocations, listOrganizations } from "../lib/api";
import { HubRequest, LiveLocation, Organization } from "../lib/types";

const CHENNAI_CENTER: [number, number] = [13.0827, 80.2707];

const CHENNAI_BOUNDS: [[number, number], [number, number]] = [
  [12.75, 79.90],
  [13.45, 80.55],
];

const URGENCY_COLORS: Record<string, string> = {
  critical: "#F62440",
  high: "#FF9800",
  medium: "#FFC107",
  low: "#4CAF50",
};

// FIX: distinct color per organization (sender)
const ORG_COLORS = ["#2196F3", "#9C27B0", "#00897B", "#EF6C00", "#C2185B", "#5D4037"];

function dotIcon(urgency?: string | null) {
  const color = URGENCY_COLORS[(urgency ?? "").toLowerCase()] ?? "#7c6a58";
  return L.divIcon({
    html: `<div style="background:${color};width:18px;height:18px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 8px rgba(0,0,0,.45);"></div>`,
    className: "",
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -10],
  });
}

function donorIcon() {
  return L.divIcon({
    html: `<div style="background:#4CAF50;width:20px;height:20px;border-radius:4px;border:2px solid #fff;box-shadow:0 0 8px rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;color:#fff;font-size:10px;font-weight:bold;">D</div>`,
    className: "",
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

function personIcon(color: string) {
  return L.divIcon({
    html: `
      <div style="position:relative;width:24px;height:24px;">
        <div style="position:absolute;inset:0;border-radius:50%;background:${color};opacity:.4;"></div>
        <div style="position:absolute;inset:6px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 8px ${color};"></div>
      </div>`,
    className: "",
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
}

interface Props {
  requests?: HubRequest[];
}

export default function ChennaiMap({ requests = [] }: Props) {
  const [locations, setLocations] = useState<LiveLocation[]>([]);
  const [orgs, setOrgs] = useState<Organization[]>([]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [locRes, orgRes] = await Promise.all([listLocations(), listOrganizations()]);
        if (!mounted) return;
        setLocations(locRes.locations);
        setOrgs(orgRes.organizations);
      } catch {
        // backend unreachable — ignore
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  // FIX: org id → real name (NGO01 → "NGO Alpha"), fallback to id
  const orgName = (id: string) => orgs.find((o) => o.organization_id === id)?.name ?? id;

  // FIX: org id → distinct color
  const orgColor = (id: string) => {
    const idx = orgs.findIndex((o) => o.organization_id === id);
    return ORG_COLORS[(idx >= 0 ? idx : 0) % ORG_COLORS.length];
  };

  const requestMarkers = requests.filter(
    (r) =>
      typeof r.latitude === "number" &&
      typeof r.longitude === "number" &&
      (r.latitude !== 0 || r.longitude !== 0)
  );

  const personMarkers = locations.filter(
    (l) => typeof l.latitude === "number" && typeof l.longitude === "number"
  );

  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-xl border border-[#FFE5BF] bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
          Live Chennai Map
        </h2>
        <span className="text-xs text-[#a1866f]">
          {requestMarkers.length} request(s) · {personMarkers.length} live worker(s)
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-4 border-b border-[#FFE5BF] bg-white px-4 py-2 text-[11px]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: "#2196F3" }} />
          <span className="font-semibold text-[#4a3a28]">Field worker (live GPS)</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded bg-[#4CAF50] text-[8px] font-bold text-white">D</span>
          <span className="font-semibold text-[#4a3a28]">Donor / Supply Pool</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-[#F62440] border-t border-dashed border-[#F62440]" />
          <span className="font-semibold text-[#F62440]">Nearest Dispatch Route</span>
        </span>
        {Object.entries(URGENCY_COLORS).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: color }} />
            <span className="font-semibold capitalize text-[#4a3a28]">{label} Need</span>
          </span>
        ))}
      </div>

      <div className="flex-1 w-full">
        <MapContainer
          center={CHENNAI_CENTER}
          zoom={12}
          minZoom={10}
          maxZoom={17}
          maxBounds={CHENNAI_BOUNDS}
          maxBoundsViscosity={1.0}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* LAYER 1: Live field-worker GPS — colored per org, real name label */}
          {personMarkers.map((l) => (
            <Marker
              key={`person-${l.organization_id}-${l.latitude}-${l.longitude}`}
              position={[l.latitude, l.longitude]}
              icon={personIcon(orgColor(l.organization_id))}
            >
              <Tooltip permanent direction="top" offset={[0, -10]}>
                {orgName(l.organization_id)}
              </Tooltip>
              <Popup>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <strong>{orgName(l.organization_id)}</strong>{" "}
                  <span style={{ color: "#a1866f" }}>({l.organization_id})</span>
                  <br />
                  Live field worker
                  <br />
                  GPS: {l.latitude.toFixed(4)}, {l.longitude.toFixed(4)}
                  <br />
                  Updated: {new Date(l.updated_at).toLocaleTimeString()}
                </div>
              </Popup>
            </Marker>
          ))}

          {/* LAYER 2: Nearest Route Polylines between Needs & Matched Donors */}
          {requestMarkers
            .filter((r) => r.type === "need" && r.matches && r.matches.length > 0)
            .map((r) =>
              (r.matches || []).map((m, idx) => {
                if (
                  typeof m.latitude === "number" &&
                  typeof m.longitude === "number" &&
                  (m.latitude !== 0 || m.longitude !== 0)
                ) {
                  return (
                    <Polyline
                      key={`route-${r.id}-${m.organization_id}-${idx}`}
                      positions={[
                        [m.latitude, m.longitude],
                        [r.latitude as number, r.longitude as number],
                      ]}
                      pathOptions={{
                        color: "#F62440",
                        weight: 3,
                        dashArray: "6, 8",
                        opacity: 0.85,
                      }}
                    >
                      <Tooltip sticky>
                        Nearest Route: {m.organization_id} → {r.location_name || r.id} ({m.distance_km ?? "?"} km away)
                      </Tooltip>
                    </Polyline>
                  );
                }
                return null;
              })
            )}

          {/* LAYER 3: Request & Donor markers */}
          {requestMarkers.map((r) => (
            <Marker
              key={`req-${r.id}-${r.latitude}-${r.longitude}`}
              position={[r.latitude as number, r.longitude as number]}
              icon={r.type === "resource" ? donorIcon() : dotIcon(r.urgency)}
            >
              <Popup>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <strong>{r.id}</strong>{" "}
                  <span style={{ color: "#a1866f" }}>({r.source})</span>
                  <br />
                  Type:{" "}
                  <span className="font-bold uppercase text-[#7c4a12]">
                    {r.type === "resource" ? "Donor Resource" : "Emergency Need"}
                  </span>
                  <br />
                  Sender:{" "}
                  <span style={{ color: orgColor(r.organization_id), fontWeight: 700 }}>
                    {orgName(r.organization_id)} ({r.organization_id})
                  </span>
                  <br />
                  GPS: {Number(r.latitude).toFixed(4)}, {Number(r.longitude).toFixed(4)}
                  <br />
                  Loc: {r.location_name ?? r.location_code}
                  <br />
                  {r.resource} × {r.quantity}
                  <br />
                  {r.type === "need" && (
                    <>
                      <span
                        style={{
                          color: URGENCY_COLORS[(r.urgency ?? "").toLowerCase()],
                          fontWeight: 700,
                        }}
                      >
                        {r.urgency} urgency
                      </span>{" "}
                      ·{" "}
                    </>
                  )}
                  Status: {r.status}
                  <br />
                  {r.plan_id && <span>Plan: {r.plan_id}</span>}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}