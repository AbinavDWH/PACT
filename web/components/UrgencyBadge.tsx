import { HubRequest } from "../lib/types";

const URGENCY_STYLES: Record<string, string> = {
  low: "bg-gray-100 text-gray-700",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const AVAILABILITY_STYLES: Record<string, string> = {
  available: "bg-green-100 text-green-800",
  limited: "bg-amber-100 text-amber-800",
  unavailable: "bg-red-100 text-red-800",
};

export default function UrgencyBadge({ request }: { request: HubRequest }) {
  if (request.type === "need" && request.urgency) {
    return (
      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${URGENCY_STYLES[request.urgency] ?? ""}`}>
        {request.urgency}
      </span>
    );
  }
  if (request.type === "resource" && request.availability) {
    return (
      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${AVAILABILITY_STYLES[request.availability] ?? ""}`}>
        {request.availability}
      </span>
    );
  }
  return <span className="text-xs text-[#a1866f]">—</span>;
}