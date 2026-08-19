"use client";

import { useState } from "react";

const INTERNAL_DATA = [
  ["Donor names & funding sources", "Financial relationships withheld"],
  ["Staff & volunteer rosters", "Personnel data protected"],
  ["Exact warehouse coordinates", "Security-sensitive locations masked"],
  ["Full inventory levels", "Exact stock counts hidden"],
  ["Operational plans & security details", "Tactical information protected"],
];

const SHARED_DATA = [
  ["Organization ID", "NGO01, CSR02, GOV03"],
  ["Rounded resource quantities", "\"100–200 units\" not \"147 units\""],
  ["Region codes", "RA, RB, RC (not exact addresses)"],
  ["ETA ranges", "\"3–4 hours\" not exact routes"],
  ["Service radius", "\"50 km coverage area\""],
];

export default function PrivacyPage() {
  const [reveal, setReveal] = useState(false);

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            Privacy Boundary
          </p>
          <h1 className="mt-1 text-3xl font-bold">Internal vs Shared Data</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            The Privacy Filter Agent ensures sensitive data never crosses into the coordination layer.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Internal */}
          <div className="rounded-xl border border-[#FFE5BF] bg-white">
            <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
              <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
                Internal Organization Data
              </h2>
              <p className="mt-1 text-xs text-[#a1866f]">Never exposed to coordination agents</p>
            </div>
            <div className="p-6">
              <ul className="space-y-3 text-sm">
                {INTERNAL_DATA.map(([title, desc]) => (
                  <li key={title} className="flex items-start gap-2">
                    <span className="mt-1 h-2 w-2 rounded-full bg-red-500" />
                    <div>
                      <div className="font-semibold">{title}</div>
                      <div className="text-xs text-[#a1866f]">{desc}</div>
                    </div>
                  </li>
                ))}
              </ul>

              {reveal && (
                <div className="mt-6 rounded-lg border-2 border-dashed border-red-300 bg-red-50 p-4">
                  <div className="text-xs font-bold uppercase text-red-700">
                    Example Withheld Data
                  </div>
                  <div className="mt-2 space-y-1 font-mono text-xs text-red-900">
                    <div>donor: "Global Health Foundation"</div>
                    <div>staff_count: 47</div>
                    <div>warehouse: 13.0827, 80.2707</div>
                    <div>exact_stock: 1247 medical_kits</div>
                  </div>
                </div>
              )}

              <button
                onClick={() => setReveal(!reveal)}
                className="mt-6 rounded-lg border border-[#e3c9a8] px-4 py-2 text-sm font-semibold text-[#7c4a12] transition hover:bg-[#FFF2DB]"
              >
                {reveal ? "Hide" : "Reveal"} Example Withheld Data
              </button>
            </div>
          </div>

          {/* Shared */}
          <div className="rounded-xl border border-[#FFE5BF] bg-white">
            <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
              <h2 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
                Shared Organization Profile
              </h2>
              <p className="mt-1 text-xs text-[#a1866f]">Safe for coordination agents to use</p>
            </div>
            <div className="p-6">
              <ul className="space-y-3 text-sm">
                {SHARED_DATA.map(([title, desc]) => (
                  <li key={title} className="flex items-start gap-2">
                    <span className="mt-1 h-2 w-2 rounded-full bg-green-500" />
                    <div>
                      <div className="font-semibold">{title}</div>
                      <div className="text-xs text-[#a1866f]">{desc}</div>
                    </div>
                  </li>
                ))}
              </ul>

              <div className="mt-6 rounded-lg border-2 border-dashed border-green-300 bg-green-50 p-4">
                <div className="text-xs font-bold uppercase text-green-700">
                  Example Shared Profile
                </div>
                <div className="mt-2 space-y-1 font-mono text-xs text-green-900">
                  <div>{"{"}</div>
                  <div className="pl-4">"organization_id": "NGO01",</div>
                  <div className="pl-4">"resources": {"{"} "M": "100-200" {"}"},</div>
                  <div className="pl-4">"eta_hours": 3,</div>
                  <div className="pl-4">"radius_km": 50</div>
                  <div>{"}"}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
          <h3 className="text-lg font-bold">How It Works</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div>
              <div className="text-sm font-semibold text-[#F62440]">1. Intake</div>
              <p className="mt-1 text-sm text-[#7c6a58]">
                Organizations submit full internal profiles with sensitive data.
              </p>
            </div>
            <div>
              <div className="text-sm font-semibold text-[#F62440]">2. Filter</div>
              <p className="mt-1 text-sm text-[#7c6a58]">
                Privacy Filter Agent strips withheld fields and rounds quantities.
              </p>
            </div>
            <div>
              <div className="text-sm font-semibold text-[#F62440]">3. Coordinate</div>
              <p className="mt-1 text-sm text-[#7c6a58]">
                Coordination agents only see the shared profile — never internal data.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}