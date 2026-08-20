"use client";

// Codec console (codec.md section 12, item 7).
//
// Paste a codec string, watch it decode and enter the pipeline. This is not a
// simulation of anything: /api/v1/sms/simulate and /api/v1/pact/ingest both
// call the same decoder and the same agents that a real handset SMS reaches --
// the only difference is which transport carried the bytes here. It was titled
// "SMS Simulator", which described the real ingest path as fake.
//
// The presets are canonical encodings from the codec spec, kept because typing
// a checksummed string by hand is not a demo. A legacy "N|NGO01|RegionA|..."
// entry lived here for backwards compatibility with a format the encoder no
// longer emits; it has been dropped.

import { useState } from "react";
import { authFetch } from "../_lib/useAgentSocket";

const PRESETS: { label: string; sms: string; note?: string }[] = [
  { label: "Trapped, critical", sms: "Q|101|7F3K|15223C03Q0|6QR6VFBQ33|7E" },
  { label: "Flood, family of 6", sms: "Q|102|A19P|10302H0SJ1|6QR9WFBPT0|70" },
  { label: "Displacement site", sms: "Q|103|C4M2|1A800M0364|728B2FBADG|64" },
  { label: "NGO offer", sms: "G|104|N001|2101Z542A|728B2FBADG|2C" },
  // Kept deliberately: it exercises the checksum rejection path, which is a
  // real behaviour worth showing, not a stand-in for one.
  { label: "Invalid checksum (rejects)",
    sms: "Q|105|7F3K|15223C03Q0|6QR6VFBQ33|XX",
    note: "expected to be rejected" },
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

export function CodecConsole() {
  const [sms, setSms] = useState(PRESETS[0].sms);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState<"sms" | "http" | null>(null);

  const send = async (transport: "sms" | "http") => {
    setBusy(transport);
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
      setBusy(null);
    }
  };

  const d = result?.decoded;
  const ok = result?.status === "accepted";
  const over = sms.length > 160;

  return (
    <section className="sim" aria-label="Send a raw message">
      <div className="simHead">
        <h3>Send a raw message</h3>
        <span className={`len ${over ? "over" : ""}`}>
          {sms.length} / 160 chars
        </span>
        <p className="simSub">
          One checksummed string, decoded and run through the live pipeline —
          the same path a handset SMS takes.
        </p>
      </div>

      <div className="presets">
        {PRESETS.map((p) => (
          <button key={p.label} className="preset"
                  aria-pressed={sms === p.sms}
                  title={p.note}
                  onClick={() => setSms(p.sms)}>
            {p.label}
          </button>
        ))}
      </div>

      {/* A real label, not a placeholder standing in for one. Visually hidden
          because the section heading already names the field, but present for
          a screen reader and for the textarea's accessible name. */}
      <label className="srOnly" htmlFor="codecInput">Codec string</label>
      <textarea
        id="codecInput"
        className="simInput"
        value={sms}
        spellCheck={false}
        aria-invalid={over}
        aria-describedby="codecLen"
        onChange={(e) => setSms(e.target.value.toUpperCase())}
        rows={2}
      />
      <span id="codecLen" className="srOnly">
        {over ? "Over the 160 character SMS limit" : "Within the SMS limit"}
      </span>

      <div className="simActions">
        <button className="sendSms" disabled={busy !== null}
                onClick={() => void send("sms")}>
          {busy === "sms" && <span className="spinner" aria-hidden="true" />}
          {busy === "sms" ? "Sending…" : "Send as SMS"}
        </button>
        <button className="sendHttp" disabled={busy !== null}
                onClick={() => void send("http")}>
          {busy === "http" && <span className="spinner" aria-hidden="true" />}
          {busy === "http" ? "Sending…" : "Send as HTTP"}
        </button>
        <span className="simHint">Same string, either transport — identical result.</span>
      </div>

      {result && (
        <div className={`simResult ${ok ? "ok" : "bad"}`} role="status" aria-live="polite">
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
