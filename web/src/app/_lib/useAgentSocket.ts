"use client";

// Single WebSocket, reduced into a map of runs keyed by trace_id.
// seq is used for ordering and dedupe only -- a client filtered to one trace
// legitimately sees gaps, so never treat a gap as a lost frame.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AGENT_LABELS, type Allocation, type DebateTurn,
  type Envelope, type Option, type Run,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const WS_BASE = API_BASE.replace(/^http/, "ws");

function emptyRun(traceId: string, ts: string): Run {
  return {
    traceId, runId: null, status: "running", summary: "", startedAt: ts,
    agentsSeen: [], bubbles: [], turns: [], options: [],
    notifications: [], errors: [], lastSeq: 0,
  };
}

function reduce(run: Run, ev: Envelope): Run {
  if (ev.seq <= run.lastSeq) return run; // dedupe across reconnect

  const p = ev.payload;
  const str = (k: string) => p[k] as string | undefined;
  const num = (k: string) => p[k] as number | undefined;

  const next: Run = { ...run, lastSeq: ev.seq, runId: ev.run_id ?? run.runId };

  switch (ev.type) {
    case "run.started":
      next.summary = str("masked_summary") ?? "";
      break;

    case "agent.entered":
      if (!next.agentsSeen.includes(ev.agent)) {
        next.agentsSeen = [...next.agentsSeen, ev.agent];
      }
      break;

    case "agent.token": {
      const delta = str("delta") ?? "";
      const last = next.bubbles[next.bubbles.length - 1];
      if (last && last.agent === ev.agent && last.streaming) {
        next.bubbles = [...next.bubbles.slice(0, -1), { ...last, text: last.text + delta }];
      } else {
        next.bubbles = [...next.bubbles, {
          key: String(ev.seq), agent: ev.agent, label: AGENT_LABELS[ev.agent],
          text: delta, streaming: true,
        }];
      }
      break;
    }

    case "agent.message": {
      const last = next.bubbles[next.bubbles.length - 1];
      const bubble = {
        key: String(ev.seq), agent: ev.agent, label: AGENT_LABELS[ev.agent],
        text: str("text") ?? "", streaming: false,
        confidence: num("confidence") ?? null,
      };
      // Finalise the bubble the tokens were streaming into.
      if (last && last.agent === ev.agent && last.streaming) {
        next.bubbles = [...next.bubbles.slice(0, -1), bubble];
      } else {
        next.bubbles = [...next.bubbles, bubble];
      }
      const structured = p.structured as Record<string, unknown> | undefined;
      if (structured?.withheld) {
        next.privacy = {
          shared: (structured.shared as string[]) ?? [],
          withheld: (structured.withheld as string[]) ?? [],
        };
      }
      break;
    }

    case "agent.tool_call":
      next.bubbles = [...next.bubbles, {
        key: String(ev.seq), agent: ev.agent, label: AGENT_LABELS[ev.agent],
        text: "", streaming: false,
        toolCall: {
          tool: str("tool") ?? "",
          args: (p.args as Record<string, unknown>) ?? {},
          result_count: num("result_count") ?? 0,
          ms: num("ms") ?? 0,
        },
      }];
      break;

    case "debate.turn":
      next.turns = [...next.turns, p as unknown as DebateTurn];
      break;

    case "debate.closed":
      next.debateWinner = str("winner");
      next.debateDissent = str("dissent");
      break;

    case "options.proposed":
      next.options = (p.options as Option[]) ?? [];
      break;

    case "decision.proposed": {
      next.decisionId = str("decision_id");
      next.chosenOptionId = str("chosen_option_id");
      next.justification = str("justification");
      const opts = p.options as Option[] | undefined;
      if (opts?.length) next.options = opts;
      break;
    }

    case "awaiting_admin":
      next.status = "awaiting_admin";
      next.decisionId = str("decision_id");
      next.gateTimeoutS = num("timeout_s");
      next.autopilot = p.autopilot as boolean | undefined;
      break;

    case "admin.action":
      next.status = "running";
      next.adminAction = {
        action: str("action") ?? "",
        admin_id: str("admin_id") ?? "",
        option_id: str("option_id"),
        note: str("note"),
      };
      break;

    case "decision.committed":
      next.committed = {
        match_id: str("match_id") ?? "",
        allocations: (p.allocations as Allocation[]) ?? [],
        unmet: num("unmet") ?? 0,
      };
      break;

    case "notify.sent":
      next.notifications = [...next.notifications, {
        channel: str("channel") ?? "",
        target_masked: str("target_masked") ?? "",
        message: str("message") ?? "",
      }];
      break;

    case "error":
      next.errors = [...next.errors, {
        agent: ev.agent, code: str("code") ?? "",
        fallback_used: p.fallback_used as boolean | undefined,
      }];
      break;

    case "run.completed":
      next.status = str("status") === "committed" ? "committed" : "rejected";
      next.msTotal = num("ms_total");
      break;
  }
  return next;
}

export function useAgentSocket() {
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [eventCount, setEventCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const lastSeqRef = useRef(0);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (closed) return;
      const q = lastSeqRef.current ? `?since=${lastSeqRef.current}` : "";
      const ws = new WebSocket(`${WS_BASE}/ws/agents${q}`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e) => {
        const ev = JSON.parse(e.data as string) as Envelope;
        if (ev.type === "hello" || ev.type === "pong" || ev.type === "decision.ack") return;
        if (typeof ev.seq === "number") {
          lastSeqRef.current = Math.max(lastSeqRef.current, ev.seq);
        }
        setEventCount((c) => c + 1);
        setRuns((prev) => {
          const cur = prev[ev.trace_id] ?? emptyRun(ev.trace_id, ev.ts);
          return { ...prev, [ev.trace_id]: reduce(cur, ev) };
        });
        setOrder((prev) => (prev.includes(ev.trace_id) ? prev : [ev.trace_id, ...prev]));
      };
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, []);

  const decide = useCallback(
    (decisionId: string, action: "approve" | "override" | "reject", optionId?: string) => {
      wsRef.current?.send(JSON.stringify({
        op: "decision", decision_id: decisionId, action,
        option_id: optionId, admin_id: "admin",
      }));
    }, []);

  const simulate = useCallback(async (body: Record<string, unknown>) => {
    await fetch(`${API_BASE}/api/v1/admin/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }, []);

  return {
    runs, order, connected, eventCount, decide, simulate,
    orderedRuns: order.map((id) => runs[id]).filter(Boolean),
  };
}
