import { HubRequest, STATUS_CODE_NAMES } from "../lib/types";
import SourceBadge from "./SourceBadge";
import StatusBadge from "./StatusBadge";
import UrgencyBadge from "./UrgencyBadge";

interface Props {
  requests: HubRequest[];
  busyId: string | null;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
}

function resourceLabel(r: HubRequest): string {
  if (r.type === "status") return r.plan_id ? `Plan ${r.plan_id}` : "—";
  return r.resource ?? r.resource_code ?? "—";
}

function qtyLabel(r: HubRequest): string {
  if (r.type === "status") {
    return r.status_code != null ? STATUS_CODE_NAMES[r.status_code] ?? `code ${r.status_code}` : "—";
  }
  return r.quantity != null ? String(r.quantity) : "—";
}

function gpsLabel(r: HubRequest): string {
  if (typeof r.latitude === "number" && typeof r.longitude === "number" && (r.latitude !== 0 || r.longitude !== 0)) {
    return `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`;
  }
  return "—";
}

export default function RequestTable({ requests, busyId, onAccept, onReject }: Props) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[#FFE5BF] bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#FFE5BF] bg-[#FFF2DB] text-left text-xs uppercase tracking-wide text-[#7c4a12]">
            <th className="px-4 py-3">ID</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Org</th>
            <th className="px-4 py-3">Location</th>
            <th className="px-4 py-3">GPS Coordinates</th>
            <th className="px-4 py-3">Resource</th>
            <th className="px-4 py-3">Qty / Detail</th>
            <th className="px-4 py-3">Priority</th>
            <th className="px-4 py-3">Source</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Action</th>
          </tr>
        </thead>
        <tbody>
          {requests.length === 0 && (
            <tr>
              <td colSpan={11} className="px-4 py-10 text-center text-[#a1866f]">
                No requests in this view.
              </td>
            </tr>
          )}
          {requests.map((r) => (
            <tr key={r.id} className="border-b border-[#FFF2DB] last:border-0 hover:bg-[#FFFAF3]">
              <td className="px-4 py-3">
                <div className="font-semibold">{r.id}</div>
                {r.sms_canonical && (
                  <div className="mt-0.5 max-w-[220px] truncate font-mono text-[10px] text-[#a1866f]" title={r.sms_canonical}>
                    {r.sms_canonical}
                  </div>
                )}
              </td>
              <td className="px-4 py-3 capitalize">{r.type}</td>
              <td className="px-4 py-3 font-medium">{r.organization_id}</td>
              <td className="px-4 py-3">
                {r.location_code ?? "—"}
                {r.location_name && r.location_name !== r.location_code && (
                  <div className="text-[11px] text-[#a1866f]">{r.location_name}</div>
                )}
              </td>
              <td className="px-4 py-3 font-mono text-[11px] text-[#4a3a28]">
                {gpsLabel(r)}
              </td>
              <td className="px-4 py-3">{resourceLabel(r)}</td>
              <td className="px-4 py-3">{qtyLabel(r)}</td>
              <td className="px-4 py-3"><UrgencyBadge request={r} /></td>
              <td className="px-4 py-3"><SourceBadge source={r.source} /></td>
              <td className="px-4 py-3"><StatusBadge status={r.status} reason={r.reject_reason} /></td>
              <td className="px-4 py-3">
                {r.status === "pending" ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => onAccept(r.id)}
                      disabled={busyId === r.id}
                      className="rounded-lg bg-[#F62440] px-3 py-1.5 text-xs font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      {busyId === r.id ? "…" : "Accept"}
                    </button>
                    <button
                      onClick={() => onReject(r.id)}
                      disabled={busyId === r.id}
                      className="rounded-lg border border-[#e3c9a8] px-3 py-1.5 text-xs font-semibold text-[#7c4a12] transition hover:bg-[#FFF2DB] disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-[#a1866f]">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}