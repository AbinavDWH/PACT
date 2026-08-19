"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { listRequests } from "../lib/api";
import { HubRequest } from "../lib/types";

// Chennai center
const CHENNAI_CENTER: [number, number] = [13.0827, 80.2707];

// Lock the map to Chennai only — users cannot pan outside
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

const TYPE_LABELS: Record<string, string> = {
  need: "Need",
  resource: "Resource",
  status: "Status",
};

// Colored dot markers (no image files needed)
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

export default function ChennaiMap() {
  const [requests, setRequests] = useState<HubRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await listRequests();
        if (!mounted) return;
        setRequests(res.requests);
        setError(null);
        setLastUpdated(new Date());
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Backend unreachable");
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const markers = requests.filter(
    (r) =>
      typeof r.latitude === "number" &&
      typeof r.longitude === "number" &&
      (r.latitude !== 0 || r.longitude !== 0)
  );

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-6xl space-y-4">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
              PACT Command Center
            </p>
            <h1 className="mt-1 text-3xl font-bold">Chennai Crisis Map</h1>
            <p className="mt-1 text-sm text-[#7c6a58]">
              OpenStreetMap locked to Chennai. Markers are field reports with GPS
              coordinates. Live updates every 3 seconds.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-[#7c6a58]">
            <a
              href="/requests"
              className="rounded-full bg-[#FFF2DB] px-4 py-1.5 font-semibold text-[#7c4a12] hover:bg-[#FFE5BF]"
            >
              Request Hub
            </a>
            <span
              className={`h-2 w-2 rounded-full ${
                error ? "bg-red-500" : "animate-pulse bg-green-500"
              }`}
            />
            {error
              ? "Backend unreachable"
              : lastUpdated
              ? `Live · ${lastUpdated.toLocaleTimeString()}`
              : "Connecting…"}
          </div>
        </header>

        <div className="flex flex-wrap items-center gap-4 rounded-xl border border-[#FFE5BF] bg-white px-4 py-3 text-xs">
          {Object.entries(URGENCY_COLORS).map(([label, color]) => (
            <span key={label} className="flex items-center gap-2">
              <span
                style={{ background: color }}
                className="inline-block h-3 w-3 rounded-full"
              />
              <span className="font-semibold capitalize">{label}</span>
            </span>
          ))}
          <span className="ml-auto text-[#a1866f]">
            {markers.length} marker(s) on map
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-[#FFE5BF]">
          <MapContainer
            center={CHENNAI_CENTER}
            zoom={12}
            minZoom={10}
            maxZoom={17}
            maxBounds={CHENNAI_BOUNDS}
            maxBoundsViscosity={1.0}
            style={{ height: "68vh", width: "100%" }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {markers.map((r) => (
              <Marker
                key={`${r.id}-${r.latitude}-${r.longitude}`}
                position={[r.latitude as number, r.longitude as number]}
                icon={dotIcon(r.urgency)}
              >
                <Popup>
                  <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                    <strong>{r.id}</strong> · {TYPE_LABELS[r.type] ?? r.type}
                    <br />
                    Org: {r.organization_id}
                    <br />
                    Location: {r.location_name ?? r.location_code}
                    <br />
                    Resource: {r.resource} × {r.quantity}
                    <br />
                    Urgency:{" "}
                    <span
                      style={{
                        color: URGENCY_COLORS[(r.urgency ?? "").toLowerCase()],
                        fontWeight: 700,
                      }}
                    >
                      {r.urgency}
                    </span>
                    <br />
                    Source: {r.source} · Status: {r.status}
                    <br />
                    <span style={{ color: "#a1866f" }}>
                      GPS: {r.latitude?.toFixed(4)}, {r.longitude?.toFixed(4)}
                    </span>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      </div>
    </main>
  );
}