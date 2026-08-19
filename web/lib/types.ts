export type RequestType = "need" | "resource" | "status";
export type RequestSource = "web" | "sms" | "android";
export type RequestStatus =
  | "pending" | "accepted" | "rejected" | "duplicate"
  | "processing" | "matched" | "allocated" | "completed";

export interface HubRequest {
  id: string;
  type: RequestType;
  seq?: string;
  organization_id: string;
  location_code?: string;
  location_name?: string;
  resource?: string;
  resource_code?: string;
  quantity?: number;
  urgency?: string;
  urgency_code?: string;
  availability?: string;
  availability_code?: string;
  plan_id?: string;
  status_code?: number;
  status: RequestStatus;
  source: RequestSource;
  payload?: Record<string, unknown>;
  checksum?: string | null;
  sms_canonical?: string | null;
  created_at: string;
  reviewed_at?: string | null;
  reject_reason?: string | null;
}

export interface PlanAllocation {
  organization_id: string;
  quantity: number;
  eta_hours: number;
}

export interface Plan {
  plan_id: string;
  request_id?: string | null;
  resource?: string;
  resource_code?: string;
  location_code?: string;
  location_name?: string;
  required_quantity?: number;
  allocated_quantity?: number;
  allocations: PlanAllocation[];
  priority?: string;
  status: string;
  created_at: string;
}

export interface ActivityEntry {
  ts: string;
  agent: string;
  message: string;
}

export const STATUS_CODE_NAMES: Record<number, string> = {
  0: "assigned", 1: "dispatched", 2: "in_transit",
  3: "delivered", 4: "blocked", 5: "cancelled",
};