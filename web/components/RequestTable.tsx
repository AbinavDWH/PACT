import { HubRequest, STATUS_CODE_NAMES } from "../lib/types";
import SourceBadge from "./SourceBadge";
import StatusBadge from "./StatusBadge";
import UrgencyBadge from "./UrgencyBadge";

interface Props {
  requests: HubRequest[];
  busyId: string | null;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onAiTriage?: (id: string) => void;
  onConfirmHandover?: (id: string, planId?: string) => void;
  onConfirmReceipt?: (id: string, planId?: string) => void;
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

// NEW: allocation result — shows success (plan + coverage) or failure (no suppliers)
function allocationCell(r: HubRequest) {
  if (r.type !== "need") return <span className="text-xs text-[#a1866f]">—</span>;

  const matched = r.total_matched ?? 0;
  const required = r.quantity ?? 0;

  if (r.status === "allocated" || r.status === "completed") {
    if (matched <= 0) {
      return (
        <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
          NO SUPPLIERS
        </span>
      );
    }
    const pct = required > 0 ? Math.round((matched / required) * 100) : 0;
    const full = matched >= required;
    return (
      <div className="text-xs">
        <span className={`rounded-full px-2 py-0.5 font-bold ${full ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
          {full ? "ALLOCATED" : "PARTIAL"}
        </span>
        <div className="mt-1 font-mono text-[11px] text-[#4a3a28]">
          {r.plan_id ?? "PLAN"} · {matched}/{required} ({pct}%)
        </div>
      </div>
    );
  }

  if (r.status === "matched") {
    return (
      <div className="text-xs">
        <span className="rounded-full bg-blue-100 px-2 py-0.5 font-bold text-blue-700">MATCHED</span>
        <div className="mt-1 font-mono text-[11px] text-[#4a3a28]">{matched}/{required} found</div>
      </div>
    );
  }

  if (r.status === "accepted" || r.status === "processing") {
    return <span className="text-xs text-[#a1866f]">agents working…</span>;
  }

  return <span className="text-xs text-[#a1866f]">—</span>;
}

export default function RequestTable({
  requests,
  busyId,
  onAccept,
  onReject,
  onAiTriage,
  onConfirmHandover,
  onConfirmReceipt,
}: Props) {
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
            <th className="px-4 py-3">Allocation</th>
            <th className="px-4 py-3">Action</th>
          </tr>
        </thead>
        <tbody>
          {requests.length === 0 && (
            <tr>
              <td colSpan={12} className="px-4 py-10 text-center text-[#a1866f]">
                No requests in this view.
              </td>
            </tr>
          )}
          {requests.map((r) => {
            const isHandedOver = ["in_transit", "dispatched", "delivered", "completed"].includes(r.status);
            const isDelivered = ["delivered", "completed"].includes(r.status);
            const isAllocatedOrTransit = ["allocated", "matched", "in_transit", "dispatched", "handed_over"].includes(r.status);

            return (
              <tr key={r.id} className="border-b border-[#FFF2DB] last:border-0 hover:bg-[#FFFAF3]">
                <td className="px-4 py-3">
                  <div className="font-semibold">{r.id}</div>
                  {r.sms_canonical && (
                    <div className="mt-0.5 max-w-[220px] truncate font-mono text-[10px] text-[#a1866f]" title={r.sms_canonical}>
                      {r.sms_canonical}
                    </div>
                  )}
                  {r.ai_triage_decision && (
                    <div className="mt-1 flex items-center gap-1 text-[10px] font-semibold" title={r.ai_triage_reason || ""}>
                      <span className={`rounded px-1.5 py-0.5 border ${
                        r.ai_triage_decision === "ACCEPT"
                          ? "border-green-300 bg-green-50 text-green-800"
                          : r.ai_triage_decision === "REJECT"
                          ? "border-red-300 bg-red-50 text-red-700"
                          : "border-[#e3c9a8] bg-[#FFF2DB] text-[#7c4a12]"
                      }`}>
                        AI: {r.ai_triage_decision}
                      </span>
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
                <td className="px-4 py-3">{allocationCell(r)}</td>
                <td className="px-4 py-3">
                  {r.status === "pending" ? (
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <button
                        onClick={() => onAccept(r.id)}
                        disabled={busyId === r.id}
                        className="rounded-lg bg-[#F62440] px-2.5 py-1 text-xs font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                      >
                        {busyId === r.id ? "…" : "Accept"}
                      </button>
                      <button
                        onClick={() => onReject(r.id)}
                        disabled={busyId === r.id}
                        className="rounded-lg border border-[#e3c9a8] px-2 py-1 text-xs font-semibold text-[#7c4a12] transition hover:bg-[#FFF2DB] disabled:opacity-50"
                      >
                        Reject
                      </button>
                      {onAiTriage && (
                        <button
                          onClick={() => onAiTriage(r.id)}
                          disabled={busyId === r.id}
                          className="rounded-lg border border-[#e3c9a8] bg-[#FFF2DB] px-2 py-1 text-xs font-bold text-[#7c4a12] transition hover:bg-[#FFE5BF] disabled:opacity-50"
                          title="Evaluate with AI Auto-Triage Agent"
                        >
                          AI Triage
                        </button>
                      )}
                    </div>
                  ) : isDelivered ? (
                    <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-800">
                      ✓ Delivered
                    </span>
                  ) : isAllocatedOrTransit ? (
                    <div className="flex flex-col gap-1">
                      {onConfirmHandover && !isHandedOver && (
                        <button
                          onClick={() => onConfirmHandover(r.id, r.plan_id || undefined)}
                          disabled={busyId === r.id}
                          className="rounded-lg bg-[#4CAF50] px-2.5 py-1 text-xs font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                        >
                          {busyId === r.id ? "…" : "Confirm Handover"}
                        </button>
                      )}
                      {onConfirmReceipt && !isDelivered && (
                        <button
                          onClick={() => onConfirmReceipt(r.id, r.plan_id || undefined)}
                          disabled={busyId === r.id}
                          className="rounded-lg bg-[#2196F3] px-2.5 py-1 text-xs font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                        >
                          {busyId === r.id ? "…" : "Confirm Received"}
                        </button>
                      )}
                      {!onConfirmHandover && !onConfirmReceipt && (
                        <span className="text-xs text-[#a1866f]">In Progress</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-[#a1866f]">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}