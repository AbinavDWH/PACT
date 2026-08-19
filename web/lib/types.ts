export type RequestType = "need" | "resource" | "status";

export type RequestStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "duplicate"
  | "processing"
  | "matched"
  | "allocated"
  | "completed";

export type RequestSource = "web" | "sms" | "android";

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

  sms_canonical?: string | null;
  checksum?: string | null;
  payload?: Record<string, unknown>;
  created_at: string;
  reviewed_at?: string | null;
  reject_reason?: string | null;
}

// NEW: live field-worker GPS from Android app
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