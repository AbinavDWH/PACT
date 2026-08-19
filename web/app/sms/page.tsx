"use client";

import { useState } from "react";
import { xorChecksum } from "../../lib/sms";

const API_URL = "http://10.142.1.232:8000";

type SmsType = "need" | "marker" | "status";

export default function SmsSimulatorPage() {
  const [smsType, setSmsType] = useState<SmsType>("need");

  // Common fields
  const [seq, setSeq] = useState("001");

  // Need fields
  const [org, setOrg] = useState("NGO01");
  const [location, setLocation] = useState("RA");
  const [resource, setResource] = useState("F");
  const [quantity, setQuantity] = useState("300");
  const [urgency, setUrgency] = useState("H");

  // Marker fields
  const [lat, setLat] = useState("13.0827");
  const [lng, setLng] = useState("80.2707");
  const [markerType, setMarkerType] = useState("CR");
  const [severity, setSeverity] = useState("9");

  // Status fields
  const [planId, setPlanId] = useState("PLAN-101");
  const [statusCode, setStatusCode] = useState("3");

  const [generatedSms, setGeneratedSms] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const generateSms = () => {
    let body = "";
    if (smsType === "need") {
      body = `N|${seq}|${org}|${location}|${resource}|${quantity}|${urgency}`;
    } else if (smsType === "marker") {
      body = `M|${seq}|${lat},${lng}|${markerType}|${severity}|${resource}${quantity}`;
    } else {
      body = `S|${seq}|${planId}|${statusCode}`;
    }
    const checksum = xorChecksum(body);
    setGeneratedSms(`${body}|${checksum}`);
    setResult(null);
  };

  const sendToGateway = async () => {
    if (!generatedSms) return;
    setSending(true);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/sms/webhook`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sms: generatedSms }),
      });
      const data = await res.json();
      setResult(`Status: ${data.status ?? res.status}\n${JSON.stringify(data, null, 2)}`);
    } catch (e) {
      setResult(`Failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            SMS Fallback Simulator
          </p>
          <h1 className="mt-1 text-3xl font-bold">Test SMS Gateway</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Generate canonical SMS payloads (per sms.md) and send them to the FastAPI SMS webhook.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Generator */}
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <h2 className="text-lg font-bold">SMS Generator</h2>

            <div className="mt-4 space-y-4">
              <div>
                <label className="text-sm font-semibold text-[#7c4a12]">Message Type</label>
                <select
                  value={smsType}
                  onChange={(e) => setSmsType(e.target.value as SmsType)}
                  className="mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm"
                >
                  <option value="need">Need Request (N)</option>
                  <option value="marker">Map Marker (M)</option>
                  <option value="status">Status Update (S)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-semibold text-[#7c4a12]">Sequence</label>
                  <input
                    type="text"
                    value={seq}
                    onChange={(e) => setSeq(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                  />
                </div>

                {smsType === "need" && (
                  <>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Org</label>
                      <input
                        type="text"
                        value={org}
                        onChange={(e) => setOrg(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Location</label>
                      <select
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm"
                      >
                        <option value="RA">RA — Region A</option>
                        <option value="RB">RB — Region B</option>
                        <option value="RC">RC — Region C</option>
                        <option value="D1">D1 — District North</option>
                        <option value="D2">D2 — District South</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Resource</label>
                      <select
                        value={resource}
                        onChange={(e) => setResource(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm"
                      >
                        <option value="F">F — Food kits</option>
                        <option value="W">W — Water kits</option>
                        <option value="M">M — Medical kits</option>
                        <option value="T">T — Tents</option>
                        <option value="B">B — Blankets</option>
                        <option value="H">H — Hygiene kits</option>
                        <option value="D">D — Medical teams</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Quantity</label>
                      <input
                        type="number"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Urgency</label>
                      <select
                        value={urgency}
                        onChange={(e) => setUrgency(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm"
                      >
                        <option value="L">L — Low</option>
                        <option value="M">M — Medium</option>
                        <option value="H">H — High</option>
                        <option value="C">C — Critical</option>
                      </select>
                    </div>
                  </>
                )}

                {smsType === "marker" && (
                  <>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Latitude</label>
                      <input
                        type="number"
                        step="0.0001"
                        value={lat}
                        onChange={(e) => setLat(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Longitude</label>
                      <input
                        type="number"
                        step="0.0001"
                        value={lng}
                        onChange={(e) => setLng(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Marker Type</label>
                      <select
                        value={markerType}
                        onChange={(e) => setMarkerType(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm"
                      >
                        <option value="CR">CR — Crisis zone</option>
                        <option value="ND">ND — Need reported</option>
                        <option value="RS">RS — Resource point</option>
                        <option value="SH">SH — Shelter</option>
                        <option value="MD">MD — Medical point</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Severity (1–10)</label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        value={severity}
                        onChange={(e) => setSeverity(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                      />
                    </div>
                  </>
                )}

                {smsType === "status" && (
                  <>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Plan ID</label>
                      <input
                        type="text"
                        value={planId}
                        onChange={(e) => setPlanId(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-[#7c4a12]">Status Code</label>
                      <select
                        value={statusCode}
                        onChange={(e) => setStatusCode(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#e3c9a8] bg-white px-3 py-2 text-sm"
                      >
                        <option value="0">0 — Assigned</option>
                        <option value="1">1 — Dispatched</option>
                        <option value="2">2 — In Transit</option>
                        <option value="3">3 — Delivered</option>
                        <option value="4">4 — Blocked</option>
                        <option value="5">5 — Cancelled</option>
                      </select>
                    </div>
                  </>
                )}
              </div>

              <button
                onClick={generateSms}
                className="w-full rounded-lg bg-[#F62440] px-4 py-3 text-sm font-bold text-white transition hover:opacity-90"
              >
                Generate SMS Payload
              </button>

              {generatedSms && (
                <div className="rounded-lg border border-[#e3c9a8] bg-[#FFFAF3] p-4">
                  <div className="text-xs font-semibold uppercase text-[#7c4a12]">Generated SMS</div>
                  <div className="mt-2 break-all font-mono text-sm text-[#F62440]">{generatedSms}</div>
                  <button
                    onClick={sendToGateway}
                    disabled={sending}
                    className="mt-3 w-full rounded-lg border border-[#e3c9a8] px-4 py-2 text-sm font-semibold text-[#7c4a12] transition hover:bg-[#FFF2DB] disabled:opacity-50"
                  >
                    {sending ? "Sending…" : "Send to SMS Gateway"}
                  </button>
                </div>
              )}

              {result && (
                <div className="rounded-lg border border-[#e3c9a8] bg-white p-4">
                  <div className="text-xs font-semibold uppercase text-[#7c4a12]">Gateway Response</div>
                  <pre className="mt-2 overflow-x-auto font-mono text-xs text-[#4a3a28]">{result}</pre>
                </div>
              )}
            </div>
          </div>

          {/* Reference examples */}
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <h2 className="text-lg font-bold">Canonical SMS Examples</h2>

            <div className="mt-4 space-y-4">
              <div className="rounded-lg border border-[#e3c9a8] bg-[#FFFAF3] p-4">
                <div className="text-xs font-semibold uppercase text-[#7c4a12]">Need Request</div>
                <div className="mt-2 font-mono text-xs">N|001|NGO01|RA|F|300|H|&lt;crc&gt;</div>
                <div className="mt-1 text-xs text-[#a1866f]">
                  Need 300 food kits at Region A with high urgency
                </div>
              </div>

              <div className="rounded-lg border border-[#e3c9a8] bg-[#FFFAF3] p-4">
                <div className="text-xs font-semibold uppercase text-[#7c4a12]">Map Marker</div>
                <div className="mt-2 font-mono text-xs">M|008|13.0827,80.2707|CR|9|F300|&lt;crc&gt;</div>
                <div className="mt-1 text-xs text-[#a1866f]">
                  Crisis zone marker at coordinates with severity 9
                </div>
              </div>

              <div className="rounded-lg border border-[#e3c9a8] bg-[#FFFAF3] p-4">
                <div className="text-xs font-semibold uppercase text-[#7c4a12]">Status Update</div>
                <div className="mt-2 font-mono text-xs">S|004|PLAN-101|3|&lt;crc&gt;</div>
                <div className="mt-1 text-xs text-[#a1866f]">
                  Plan PLAN-101 status: delivered (code 3)
                </div>
              </div>

              <div className="rounded-lg border-2 border-dashed border-[#F62440] bg-red-50 p-4">
                <div className="text-xs font-bold uppercase text-[#F62440]">Checksum Rule</div>
                <div className="mt-2 text-xs">
                  XOR checksum over the message body (before the final pipe), formatted as 2 uppercase
                  hex characters. The generator computes this automatically, so generated payloads
                  always validate.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}