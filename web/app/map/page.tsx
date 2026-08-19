"use client";

import dynamic from "next/dynamic";

const ChennaiMap = dynamic(() => import("../../components/ChennaiMap"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-screen items-center justify-center bg-[#FFFAF3] text-[#7c6a58]">
      Loading Chennai map…
    </div>
  ),
});

export default function MapPage() {
  return <ChennaiMap />;
}