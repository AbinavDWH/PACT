export type RequestType = "need" | "resource" | "status";

export type RequestStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "duplicate"
  | "processing"
  | "matched"
  | "allocated"
  | "waiting"
  | "in_transit"
  | "dispatched"
  | "handed_over"
  | "delivered"
  | "completed";

export type RequestSource = "web" | "sms" | "android";

export interface OrgMatch {
  organization_id: string;
  quantity: number;
  eta_hours: number;
  distance_km?: number;
  latitude?: number;
  longitude?: number;
}

export interface Organization {
  organization_id: string;
  name: string;
  resources: Record<string, number>;
  eta_hours: number;
  radius_km: number;
  latitude?: number;
  longitude?: number;
}

export interface HubRequest {
  id: string;
  type: RequestType;
  seq: string;
  organization_id: string;
  status: RequestStatus;
  source: RequestSource;

  location_code?: string | null;
  location_name?: string | null;
  resource?: string | null;
  resource_code?: string | null;
  quantity?: number | null;

  urgency?: string | null;
  urgency_code?: string | null;

  availability?: string | null;
  availability_code?: string | null;

  plan_id?: string | null;
  status_code?: number | null;

  latitude?: number | null;
  longitude?: number | null;

  matches?: OrgMatch[] | null;
  total_matched?: number | null;

  sms_canonical?: string | null;
  checksum?: string | null;
  payload?: Record<string, unknown>;
  created_at: string;
  reviewed_at?: string | null;
  reject_reason?: string | null;

  handed_over_at?: string | null;
  handed_over_by?: string | null;
  received_at?: string | null;
  received_by?: string | null;

  ai_triage_decision?: "ACCEPT" | "REJECT" | "HOLD" | null;
  ai_triage_reason?: string | null;
  ai_triage_confidence?: number | null;
  ai_triage_flags?: string[] | null;
}

export interface AiTriageResult {
  id: string;
  decision: "ACCEPT" | "REJECT" | "HOLD";
  accepted: boolean;
  status: string;
  confidence: number;
  reason: string;
  request: HubRequest;
}

export interface AiTriageBatchResponse {
  processed: number;
  accepted: number;
  rejected: number;
  held: number;
  message: string;
  results: AiTriageResult[];
}

// NEW: body for POST /api/v1/requests (Donor Portal)
export interface CreateRequestBody {
  type: RequestType;
  organization_id: string;
  seq?: string | null;
  location?: string | null;
  resource?: string | null;
  quantity?: number | null;
  urgency?: string | null;
  availability_status?: string | null;
  plan_id?: string | null;
  status_code?: number | null;
  source?: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface LiveLocation {
  organization_id: string;
  latitude: number;
  longitude: number;
  updated_at: string;
}

export interface Allocation {
  organization_id: string;
  quantity: number;
  eta_hours: number;
  distance_km?: number;
  latitude?: number;
  longitude?: number;
}

export interface Plan {
  plan_id: string;
  request_id?: string | null;
  resource: string;
  resource_code: string;
  location_code?: string | null;
  location_name?: string | null;
  required_quantity: number;
  allocated_quantity: number;
  allocations: Allocation[];
  priority?: string | null;
  status: string;
  created_at: string;
  ai_summary?: string | null;
  ai_risks?: string | null;
  distance_km?: number | null;
  handed_over_at?: string | null;
  handed_over_by?: string | null;
  received_at?: string | null;
  received_by?: string | null;
}

export interface ActivityEntry {
  ts: string;
  agent: string;
  message: string;
}

export const STATUS_CODE_NAMES: Record<number, string> = {
  0: "assigned",
  1: "dispatched",
  2: "in_transit",
  3: "delivered",
  4: "blocked",
  5: "cancelled",
};

export const RESOURCE_CODE_LABELS: Record<string, string> = {
  F: "Food kits",
  W: "Water kits",
  M: "Medical kits",
  T: "Tents",
  B: "Blankets",
  H: "Hygiene kits",
  D: "Medical teams",
  U: "Unknown",
};