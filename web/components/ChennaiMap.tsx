"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Tooltip } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { listLocations } from "../lib/api";
import { HubRequest, LiveLocation } from "../lib/types";

// Chennai center
const CHENNAI_CENTER: [number, number] = [13.0827, 80.2707];

// Lock the map to Chennai only
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

// Blue = live field worker (person)
const PERSON_COLOR = "#2196F3";

const TYPE_LABELS: Record<string, string> = {
  need: "Need",
  resource: "Resource",
  status: "Status",
};

// Request marker: colored dot by urgency
function dotIcon(urgency?: string) {
  const color = URGENCY_COLORS[(urgency ?? "").toLowerCase()] ?? "#7c6a58";
  return L.divIcon({
    html: `<div style="background:${color};width:18px;height:18px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 8px rgba(0,0,0,.45);"></div>`,
    className: "",
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -10],
  });
}

// Person marker: blue pulsing dot
function personIcon() {
  return L.divIcon({
    html: `
      <div style="position:relative;width:24px;height:24px;">
        <div style="position:absolute;inset:0;border-radius:50%;background:${PERSON_COLOR};opacity:.4;"></div>
        <div style="position:absolute;inset:6px;border-radius:50%;background:${PERSON_COLOR};border:2px solid #fff;box-shadow:0 0 8px rgba(33,150,243,.9);"></div>
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

  // Poll live worker GPS every 3 seconds
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await listLocations();
        if (mounted) setLocations(res.locations);
      } catch {
        // backend unreachable — ignore silently
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

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

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 border-b border-[#FFE5BF] bg-white px-4 py-2 text-[11px]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: PERSON_COLOR }} />
          <span className="font-semibold text-[#4a3a28]">Field worker (live GPS)</span>
        </span>
        {Object.entries(URGENCY_COLORS).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: color }} />
            <span className="font-semibold capitalize text-[#4a3a28]">{label}</span>
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

          {/* LAYER 1: Live field-worker GPS (blue person markers with org label) */}
          {personMarkers.map((l) => (
            <Marker
              key={`person-${l.organization_id}-${l.latitude}-${l.longitude}`}
              position={[l.latitude, l.longitude]}
              icon={personIcon()}
            >
              <Tooltip permanent direction="top" offset={[0, -10]}>
                {l.organization_id}
              </Tooltip>
              <Popup>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <strong>{l.organization_id}</strong> — live field worker
                  <br />
                  GPS: {l.latitude.toFixed(4)}, {l.longitude.toFixed(4)}
                  <br />
                  Updated: {new Date(l.updated_at).toLocaleTimeString()}
                </div>
              </Popup>
            </Marker>
          ))}

          {/* LAYER 2: Request markers (colored by urgency) */}
          {requestMarkers.map((r) => (
            <Marker
              key={`req-${r.id}-${r.latitude}-${r.longitude}`}
              position={[r.latitude as number, r.longitude as number]}
              icon={dotIcon(r.urgency)}
            >
              <Popup>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <strong>{r.id}</strong>{" "}
                  <span style={{ color: "#a1866f" }}>({r.source})</span>
                  <br />
                  Org: {r.organization_id}
                  <br />
                  Loc: {r.location_name ?? r.location_code}
                  <br />
                  {r.resource} × {r.quantity}
                  <br />
                  <span
                    style={{
                      color: URGENCY_COLORS[(r.urgency ?? "").toLowerCase()],
                      fontWeight: 700,
                    }}
                  >
                    {r.urgency} urgency
                  </span>
                  <br />
                  Status: {r.status}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}