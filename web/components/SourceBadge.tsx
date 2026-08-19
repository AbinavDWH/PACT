const STYLES: Record<string, string> = {
  web: "bg-[#FFE5BF] text-[#7c4a12]",
  sms: "bg-amber-200 text-amber-900",
  android: "bg-green-200 text-green-900",
};

export default function SourceBadge({ source }: { source: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase ${STYLES[source] ?? "bg-gray-200 text-gray-700"}`}>
      {source}
    </span>
  );
}