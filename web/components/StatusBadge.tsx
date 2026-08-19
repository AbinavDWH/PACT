const STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  accepted: "bg-blue-100 text-blue-800",
  processing: "bg-indigo-100 text-indigo-800",
  matched: "bg-violet-100 text-violet-800",
  allocated: "bg-teal-100 text-teal-800",
  completed: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  duplicate: "bg-gray-200 text-gray-700",
};

export default function StatusBadge({ status, reason }: { status: string; reason?: string | null }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${STYLES[status] ?? "bg-gray-100 text-gray-700"}`}
      title={reason ?? undefined}
    >
      {status}{reason ? ` · ${reason}` : ""}
    </span>
  );
}