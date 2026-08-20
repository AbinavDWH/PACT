// Wire types. Mirrors agents.md section 3.1 / 3.2 exactly. The event contract
// is what decouples this client from the pipeline: the agents behind it are the
// live Groq ones, and nothing here would change if they were swapped again.

export type AgentId =
  | "system" | "a0_intake" | "a1_dedupe" | "a2_triage" | "a3_geo" | "a4_advocates"
  | "a5_solver" | "a6_arbiter" | "a7_privacy" | "a8_gate" | "a9_narrator"
  | "a10_verify" | "a11_replanner";

export type EventType =
  | "hello" | "pong" | "decision.ack"
  | "run.started" | "agent.entered" | "agent.thinking" | "agent.token" | "agent.message"
  | "agent.tool_call" | "debate.opened" | "debate.turn" | "debate.closed"
  | "options.proposed" | "decision.proposed" | "awaiting_admin" | "admin.action"
  | "decision.committed" | "privacy.reveal" | "notify.sent" | "verify.result"
  | "replan.triggered" | "run.completed" | "error";

export interface Envelope {
  v: number;
  seq: number;
  ts: string;
  trace_id: string;
  run_id: string | null;
  agent: AgentId;
  type: EventType;
  payload: Record<string, unknown>;
  org_id?: string;
}

export interface Allocation {
  cand_id?: string;
  name: string;
  resource: string;
  qty: number;
  eta_min: number;
}

export interface Option {
  option_id: string;
  label: string;
  allocations: Allocation[];
  coverage_pct: number;
  total_eta: number;
  score: number;
}

export interface DebateTurn {
  debate_id: string;
  turn_no: number;
  speaker: string;
  stance: "for" | "against" | "neutral";
  claim: string;
  evidence: { field: string; value: unknown }[];
  rebuts: string | null;
}

export interface Bubble {
  key: string;
  agent: AgentId;
  label: string;
  text: string;
  streaming: boolean;
  confidence?: number | null;
  toolCall?: { tool: string; args: Record<string, unknown>; result_count: number; ms: number };
}

export type RunStatus =
  | "running" | "awaiting_admin" | "committed" | "rejected" | "error";

export interface Run {
  traceId: string;
  runId: string | null;
  status: RunStatus;
  summary: string;
  startedAt: string;
  agentsSeen: AgentId[];
  bubbles: Bubble[];
  turns: DebateTurn[];
  debateWinner?: string;
  debateDissent?: string;
  options: Option[];
  chosenOptionId?: string;
  justification?: string;
  decisionId?: string;
  gateTimeoutS?: number;
  autopilot?: boolean;
  adminAction?: { action: string; admin_id: string; option_id?: string; note?: string };
  committed?: { match_id: string; allocations: Allocation[]; unmet: number };

  // A7's own report, measured off the real payload. `fieldsRedacted` and
  // `byField` are what separate a working redactor from the fixed list this
  // panel used to show -- which looked identical whether A7 did anything or
  // not. If a rule stops matching, the count drops here.
  privacy?: {
    shared: string[];
    withheld: string[];
    masked: string[];
    fieldsRedacted: number;
    byField: Record<string, number>;
    orgBlockedTypes: string[];
  };

  // The reveal transition: masked -> exact, and only on acceptance.
  reveals: {
    matchId: string;
    to: string;
    fields: string[];
    audienceBefore?: string;
    audienceAfter?: string;
    trigger?: string;
    ts: string;
  }[];

  notifications: {
    channel: string;
    target_masked: string;
    message: string;
    route?: string;          // org_portal | direct_volunteer
    state?: string;          // awaiting_assignment | pending_accept
    acceptableNow?: boolean;
    detail?: string;
  }[];

  errors: { agent: string; code: string; fallback_used?: boolean }[];

  // Positions for the map panel. Whatever the stream carried: the admin
  // audience receives exact coordinates by policy, and every other audience is
  // redacted server-side before reaching any client.
  requestPoint?: { lat: number; lon: number };
  candidates?: {
    cand_id: string; name: string;
    lat?: number | null; lon?: number | null;
    distance_km?: number; eta_minutes?: number;
  }[];

  // False means $geoNear returned nothing and the run used hardcoded fixtures.
  // The pipeline continues either way, so without surfacing it an operator
  // cannot tell that the one real database query stopped returning rows.
  geoLive?: boolean;
  cluster?: { duplicate: boolean; size: number };
  llmAgents?: Record<string, boolean>;
  msTotal?: number;
  lastSeq: number;
}

export const AGENT_LABELS: Record<AgentId, string> = {
  system: "System",
  a0_intake: "Intake",
  a1_dedupe: "Dedupe",
  a2_triage: "Triage",
  a3_geo: "Geo Search",
  a4_advocates: "Advocates",
  a5_solver: "Solver",
  a6_arbiter: "Arbiter",
  a7_privacy: "Privacy",
  a8_gate: "Admin Gate",
  a9_narrator: "Narrator",
  a10_verify: "Verification",
  a11_replanner: "Replanner",
};

// Deterministic agents. Rendered differently: these produce the numbers, and
// that distinction is the core of the design story (agents.md section 2.1).
export const DETERMINISTIC: AgentId[] = [
  "a0_intake", "a1_dedupe", "a3_geo", "a5_solver", "a7_privacy", "a11_replanner",
];
