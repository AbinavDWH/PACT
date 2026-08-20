"use client";

// SMS simulator (codec.md section 12, item 7).
//
// Paste a codec string, watch it decode and enter the same pipeline an HTTP
// request would. This is the demo beat: hold the 35 characters up against the
// 160-character SMS limit, then send it over the "SMS" path and watch the
// identical deliberation appear in the live stream.

import { useState } from "react";
import { authFetch } from "../_lib/useAgentSocket";

const PRESETS: { label: string; sms: string }[] = [
  { label: "Trapped, critical", sms: "Q|101|7F3K|15223C03Q0|6QR6VFBQ33|7E" },
  { label: "Flood, family of 6", sms: "Q|102|A19P|10302H0SJ1|6QR9WFBPT0|70" },
  { label: "Displacement site", sms: "Q|103|C4M2|1A800M0364|728B2FBADG|64" },
  { label: "NGO offer", sms: "G|104|N001|2101Z542A|728B2FBADG|2C" },
  { label: "Legacy N (demo compat)", sms: "N|NGO01|RegionA|food|300|H" },
  { label: "Bad checksum", sms: "Q|105|7F3K|15223C03Q0|6QR6VFBQ33|XX" },
];

type Result = Record<string, unknown> & {
  status?: string;
  error?: string;
  detail?: string;
  mode?: string;
  trace_id?: string;
  duplicate?: boolean;
  priority_score?: number;
  decoded?: Record<string, unknown>;
  needs?: { resource: string; quantity: number }[];
  warnings?: { code: string; field: string; value: string }[];
};

export function SmsSimulator() {
  const [sms, setSms] = useState(PRESETS[0].sms);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);

  const send = async (transport: "sms" | "http") => {
    setBusy(true);
    setResult(null);
    try {
      const res = await authFetch(
        transport === "sms" ? "/api/v1/sms/simulate" : "/api/v1/pact/ingest",
        {
          method: "POST",
          body: JSON.stringify(
            transport === "sms" ? { sms } : { payload: sms, transport: "http" },
          ),
        },
      );
      setResult((await res.json()) as Result);
    } catch (e) {
      setResult({ status: "error", error: "NETWORK", detail: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const d = result?.decoded;
  const ok = result?.status === "accepted";

  return (
    <section className="sim">
      <div className="simHead">
        <h3>SMS Simulator</h3>
        <span className={`len ${sms.length > 160 ? "over" : ""}`}>
          {sms.length} / 160 chars
        </span>
      </div>

      <div className="presets">
        {PRESETS.map((p) => (
          <button key={p.label} className="preset" onClick={() => setSms(p.sms)}>
            {p.label}
          </button>
        ))}
      </div>

      <textarea
        className="simInput"
        value={sms}
        spellCheck={false}
        onChange={(e) => setSms(e.target.value.toUpperCase())}
        rows={2}
      />

      <div className="simActions">
        <button className="sendSms" disabled={busy} onClick={() => void send("sms")}>
          {busy ? "Sending…" : "Send as SMS"}
        </button>
        <button className="sendHttp" disabled={busy} onClick={() => void send("http")}>
          Send as HTTP
        </button>
        <span className="simHint">Same string, either transport — identical result.</span>
      </div>

      {result && (
        <div className={`simResult ${ok ? "ok" : "bad"}`}>
          <div className="simStatus">
            {ok ? "accepted" : `rejected — ${result.error}`}
            {result.mode ? ` · ${result.mode}` : ""}
            {result.duplicate ? " · duplicate suppressed" : ""}
            {result.trace_id ? ` · ${result.trace_id}` : ""}
          </div>

          {result.detail && <div className="simDetail">{result.detail}</div>}
          {typeof result.expected_checksum === "string" && (
            <div className="simDetail">
              expected {String(result.expected_checksum)}, received{" "}
              {String(result.received_checksum)}
            </div>
          )}

          {d && (
            <dl className="simFields">
              {(
                [
                  ["situation", d.situation],
                  ["people", d.people_est],
                  ["injury", d.injury],
                  ["mobility", d.mobility],
                  ["urgency", d.urgency],
                  ["position", d.latitude != null ? `${d.latitude}, ${d.longitude}` : d.location_name],
                  ["priority", result.priority_score],
                ] as [string, unknown][]
              )
                .filter(([, v]) => v !== undefined && v !== null)
                .map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{String(v)}</dd>
                  </div>
                ))}
            </dl>
          )}

          {result.needs && result.needs.length > 0 && (
            <div className="simFanout">
              <span className="fanLabel">fan-out</span>
              {result.needs.map((n) => (
                <span key={n.resource} className="fanItem">
                  {n.quantity} × {n.resource.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}

          {result.warnings?.map((w, i) => (
            <div key={i} className="simWarn">
              {w.code}: {w.field} = {w.value} — decoded partially, request still accepted
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
