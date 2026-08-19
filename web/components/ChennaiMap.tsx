"use client";

import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { HubRequest } from "../lib/types";

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

interface Props {
  requests: HubRequest[];
}

export default function ChennaiMap({ requests }: Props) {
  const markers = requests.filter(
    (r) =>
      typeof r.latitude === "number" &&
      typeof r.longitude === "number" &&
      (r.latitude !== 0 || r.longitude !== 0)
  );

  return (
    <div className="h-full w-full overflow-hidden rounded-xl border border-[#FFE5BF] bg-white shadow-sm flex flex-col">
      <div className="flex items-center justify-between border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">Live Chennai Map</h2>
        <span className="text-xs text-[#a1866f]">{markers.length} active marker(s)</span>
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
          {markers.map((r) => (
            <Marker
              key={`${r.id}-${r.latitude}-${r.longitude}`}
              position={[r.latitude as number, r.longitude as number]}
              icon={dotIcon(r.urgency)}
            >
              <Popup>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <strong>{r.id}</strong> <span style={{color: '#a1866f'}}>({r.source})</span><br/>
                  Org: {r.organization_id}<br/>
                  Loc: {r.location_name ?? r.location_code}<br/>
                  {r.resource} × {r.quantity} <br/>
                  <span style={{ color: URGENCY_COLORS[(r.urgency ?? "").toLowerCase()], fontWeight: 700 }}>
                    {r.urgency} urgency
                  </span>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}