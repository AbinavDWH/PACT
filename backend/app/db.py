"""
ResiLink SQLite Persistence Engine
Zero-dependency persistent database for humanitarian coordination history,
requests, organizations, plans, and SMS gateway audit trails.
"""

import sqlite3
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resilink.db"))

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Requests Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                seq TEXT,
                organization_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'web',
                location_code TEXT,
                location_name TEXT,
                resource TEXT,
                resource_code TEXT,
                quantity INTEGER DEFAULT 0,
                urgency TEXT,
                urgency_code TEXT,
                availability TEXT,
                availability_code TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                plan_id TEXT,
                latitude REAL,
                longitude REAL,
                sms_canonical TEXT,
                checksum TEXT,
                from_number TEXT,
                reject_reason TEXT,
                sync_mode TEXT DEFAULT 'sms_and_internet',
                ai_priority_note TEXT,
                ai_flag_json TEXT,
                ai_match_reasoning TEXT,
                ai_supply_status TEXT,
                total_matched INTEGER DEFAULT 0,
                matches_json TEXT DEFAULT '[]',
                payload_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # 2. Organizations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                organization_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                resources_json TEXT NOT NULL DEFAULT '{}',
                eta_hours INTEGER DEFAULT 4,
                radius_km INTEGER DEFAULT 50,
                phone TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 3. Plans Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id TEXT PRIMARY KEY,
                request_id TEXT,
                resource TEXT,
                resource_code TEXT,
                location_code TEXT,
                location_name TEXT,
                required_quantity INTEGER DEFAULT 0,
                allocated_quantity INTEGER DEFAULT 0,
                allocations_json TEXT DEFAULT '[]',
                priority TEXT,
                status TEXT NOT NULL DEFAULT 'ready_for_dispatch',
                ai_summary TEXT,
                ai_risks TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 4. Outbound SMS Queue Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outbound_sms (
                id TEXT PRIMARY KEY,
                to_number TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'allocation',
                plan_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                dispatched_at TEXT,
                error TEXT
            )
        """)

        # 5. Gateway Activity Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gateway_logs (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                direction TEXT NOT NULL,
                from_to TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT
            )
        """)

        # 6. Agent Activity Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                agent TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)

        # 7. Counters / Sequences Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sequence_counters (
                key TEXT PRIMARY KEY,
                current_value INTEGER NOT NULL
            )
        """)

        conn.commit()


# ─────────────────────────────────────────────────────────
# Counters & Sequences
# ─────────────────────────────────────────────────────────

def get_next_sequence(key: str, default_start: int = 1) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_value FROM sequence_counters WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            val = default_start
            cursor.execute("INSERT INTO sequence_counters (key, current_value) VALUES (?, ?)", (key, val))
        else:
            val = row["current_value"] + 1
            cursor.execute("UPDATE sequence_counters SET current_value = ? WHERE key = ?", (val, key))
        conn.commit()
        return val


# ─────────────────────────────────────────────────────────
# Requests DAO
# ─────────────────────────────────────────────────────────

def save_request(rec: dict):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO requests (
                id, type, seq, organization_id, source,
                location_code, location_name, resource, resource_code,
                quantity, urgency, urgency_code, availability, availability_code,
                status, plan_id, latitude, longitude, sms_canonical, checksum,
                from_number, reject_reason, sync_mode, ai_priority_note,
                ai_flag_json, ai_match_reasoning, ai_supply_status,
                total_matched, matches_json, payload_json,
                created_at, reviewed_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                type = excluded.type,
                seq = excluded.seq,
                organization_id = excluded.organization_id,
                source = excluded.source,
                location_code = excluded.location_code,
                location_name = excluded.location_name,
                resource = excluded.resource,
                resource_code = excluded.resource_code,
                quantity = excluded.quantity,
                urgency = excluded.urgency,
                urgency_code = excluded.urgency_code,
                availability = excluded.availability,
                availability_code = excluded.availability_code,
                status = excluded.status,
                plan_id = excluded.plan_id,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                sms_canonical = excluded.sms_canonical,
                checksum = excluded.checksum,
                from_number = excluded.from_number,
                reject_reason = excluded.reject_reason,
                sync_mode = excluded.sync_mode,
                ai_priority_note = excluded.ai_priority_note,
                ai_flag_json = excluded.ai_flag_json,
                ai_match_reasoning = excluded.ai_match_reasoning,
                ai_supply_status = excluded.ai_supply_status,
                total_matched = excluded.total_matched,
                matches_json = excluded.matches_json,
                payload_json = excluded.payload_json,
                reviewed_at = excluded.reviewed_at,
                updated_at = excluded.updated_at
        """, (
            rec.get("id"),
            rec.get("type", "need"),
            rec.get("seq"),
            rec.get("organization_id", "UNKNOWN"),
            rec.get("source", "web"),
            rec.get("location_code"),
            rec.get("location_name"),
            rec.get("resource"),
            rec.get("resource_code"),
            int(rec.get("quantity") or 0),
            rec.get("urgency"),
            rec.get("urgency_code"),
            rec.get("availability"),
            rec.get("availability_code"),
            rec.get("status", "pending"),
            rec.get("plan_id"),
            rec.get("latitude"),
            rec.get("longitude"),
            rec.get("sms_canonical"),
            rec.get("checksum"),
            rec.get("from_number"),
            rec.get("reject_reason"),
            rec.get("sync_mode", "sms_and_internet"),
            rec.get("ai_priority_note"),
            json.dumps(rec.get("ai_flag")) if rec.get("ai_flag") else None,
            rec.get("ai_match_reasoning"),
            rec.get("ai_supply_status"),
            int(rec.get("total_matched") or 0),
            json.dumps(rec.get("matches") or []),
            json.dumps(rec.get("payload") or {}),
            rec.get("created_at", now_iso()),
            rec.get("reviewed_at"),
            now_iso()
        ))
        conn.commit()

def get_request(request_id: str) -> Optional[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_request_dict(row)

def load_all_requests() -> Dict[str, dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests ORDER BY created_at ASC")
        return {row["id"]: _row_to_request_dict(row) for row in cursor.fetchall()}

def _row_to_request_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("matches_json"):
        try:
            d["matches"] = json.loads(d["matches_json"])
        except Exception:
            d["matches"] = []
    if d.get("payload_json"):
        try:
            d["payload"] = json.loads(d["payload_json"])
        except Exception:
            d["payload"] = {}
    if d.get("ai_flag_json"):
        try:
            d["ai_flag"] = json.loads(d["ai_flag_json"])
        except Exception:
            d["ai_flag"] = None
    return d


# ─────────────────────────────────────────────────────────
# Organizations DAO
# ─────────────────────────────────────────────────────────

def save_organization(org_id: str, org_data: dict):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO organizations (
                organization_id, name, resources_json, eta_hours, radius_km, phone, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id) DO UPDATE SET
                name = excluded.name,
                resources_json = excluded.resources_json,
                eta_hours = excluded.eta_hours,
                radius_km = excluded.radius_km,
                phone = excluded.phone,
                updated_at = excluded.updated_at
        """, (
            org_id.upper(),
            org_data.get("name", org_id),
            json.dumps(org_data.get("resources") or {}),
            int(org_data.get("eta_hours") or 4),
            int(org_data.get("radius_km") or 50),
            org_data.get("phone", ""),
            org_data.get("created_at", now_iso()),
            now_iso()
        ))
        conn.commit()

def load_all_organizations() -> Dict[str, dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organizations")
        result = {}
        for row in cursor.fetchall():
            res_dict = {}
            if row["resources_json"]:
                try:
                    res_dict = json.loads(row["resources_json"])
                except Exception:
                    pass
            result[row["organization_id"]] = {
                "name": row["name"],
                "resources": res_dict,
                "eta_hours": row["eta_hours"],
                "radius_km": row["radius_km"],
                "phone": row["phone"]
            }
        return result


# ─────────────────────────────────────────────────────────
# Plans DAO
# ─────────────────────────────────────────────────────────

def save_plan(plan: dict):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO plans (
                plan_id, request_id, resource, resource_code, location_code, location_name,
                required_quantity, allocated_quantity, allocations_json, priority, status,
                ai_summary, ai_risks, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                request_id = excluded.request_id,
                resource = excluded.resource,
                resource_code = excluded.resource_code,
                location_code = excluded.location_code,
                location_name = excluded.location_name,
                required_quantity = excluded.required_quantity,
                allocated_quantity = excluded.allocated_quantity,
                allocations_json = excluded.allocations_json,
                priority = excluded.priority,
                status = excluded.status,
                ai_summary = excluded.ai_summary,
                ai_risks = excluded.ai_risks,
                updated_at = excluded.updated_at
        """, (
            plan.get("plan_id"),
            plan.get("request_id"),
            plan.get("resource"),
            plan.get("resource_code"),
            plan.get("location_code"),
            plan.get("location_name"),
            int(plan.get("required_quantity") or 0),
            int(plan.get("allocated_quantity") or 0),
            json.dumps(plan.get("allocations") or []),
            plan.get("priority"),
            plan.get("status", "ready_for_dispatch"),
            plan.get("ai_summary"),
            plan.get("ai_risks"),
            plan.get("created_at", now_iso()),
            now_iso()
        ))
        conn.commit()

def load_all_plans() -> Dict[str, dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plans ORDER BY created_at ASC")
        result = {}
        for row in cursor.fetchall():
            d = dict(row)
            if d.get("allocations_json"):
                try:
                    d["allocations"] = json.loads(d["allocations_json"])
                except Exception:
                    d["allocations"] = []
            result[d["plan_id"]] = d
        return result


# ─────────────────────────────────────────────────────────
# Outbound SMS Queue DAO
# ─────────────────────────────────────────────────────────

def save_outbound_sms(sms_item: dict):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO outbound_sms (
                id, to_number, message, type, plan_id, status, created_at, dispatched_at, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                dispatched_at = excluded.dispatched_at,
                error = excluded.error
        """, (
            sms_item.get("id"),
            sms_item.get("to_number"),
            sms_item.get("message"),
            sms_item.get("type", "allocation"),
            sms_item.get("plan_id"),
            sms_item.get("status", "pending"),
            sms_item.get("created_at", now_iso()),
            sms_item.get("dispatched_at"),
            sms_item.get("error")
        ))
        conn.commit()

def load_all_outbound_sms() -> Dict[str, dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outbound_sms ORDER BY created_at ASC")
        return {row["id"]: dict(row) for row in cursor.fetchall()}


# ─────────────────────────────────────────────────────────
# Gateway Logs DAO
# ─────────────────────────────────────────────────────────

def save_gateway_log(log_item: dict):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO gateway_logs (id, ts, direction, from_to, message, status, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            log_item.get("id"),
            log_item.get("ts", now_iso()),
            log_item.get("direction", "INBOUND"),
            log_item.get("from_to", "Unknown"),
            log_item.get("message", ""),
            log_item.get("status", "RECEIVED"),
            log_item.get("detail", "")
        ))
        conn.commit()

def load_gateway_logs(limit: int = 300) -> List[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gateway_logs ORDER BY ts DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()][::-1]


# ─────────────────────────────────────────────────────────
# Agent Activity DAO
# ─────────────────────────────────────────────────────────

def save_activity(agent: str, message: str, ts: str = None) -> dict:
    timestamp = ts or now_iso()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_activities (ts, agent, message)
            VALUES (?, ?, ?)
        """, (timestamp, agent, message))
        conn.commit()
        return {"ts": timestamp, "agent": agent, "message": message}

def load_activities(limit: int = 300) -> List[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ts, agent, message FROM agent_activities ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()][::-1]
