"use client";

// Organization portal.
//
// Deliberately narrower than the admin portal. An organization sees the
// allocations made to it, the roster that joined with its group code, and
// nothing else -- no cross-org debate, no rival stock, no seeker contact until
// its own helper accepts. That boundary is enforced server-side (the endpoints
// derive org_id from the token, not the URL); this screen makes it visible.

import { useCallback, useEffect, useState } from "react";
import {
  orgFetch, useOrgSession, type OrgSession,
} from "../_lib/useOrgSession";
import "../admin/admin.css";
import "./org.css";

interface Allocation {
  resource?: string;
  qty?: number;
  eta_min?: number;
  name?: string;
  state?: string;
}

interface Assignment {
  match_id: string;
  request_id?: string;
  allocation?: Allocation;
  state?: string;
  assigned_helper_id?: string | null;
  justification?: string;
  seeker?: Record<string, unknown> | null;
}

interface RosterMember {
  helper_id: string;
  uid?: string;
  name?: string;
  status?: string;
  capabilities?: string[];
}

export default function OrgPortal() {
  const { session, ready, login, logout } = useOrgSession();
  return !ready ? null : session ? (
    <Dashboard session={session} logout={logout} />
  ) : (
    <Login login={login} />
  );
}

function Login({ login }: {
  login: (u: string, p: string) => Promise<{ ok: boolean; error?: string }>;
}) {
  const [username, setUsername] = useState("sanjeevani");
  const [password, setPassword] = useState("pact-org");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const r = await login(username.trim(), password);
    if (!r.ok) setError(r.error ?? "LOGIN_FAILED");
    setBusy(false);
  };

  return (
    <div className="admin orgLoginWrap">
      <form className="orgLogin" onSubmit={submit}>
        <div className="brand">
          <span className="mark">PACT</span>
          <span className="sub">Organization Portal</span>
        </div>
        <p className="orgLoginHint">
          Sign in as your organization. You will see only your own assignments —
          never another organization&rsquo;s.
        </p>
        <label>
          Organization login
          <input value={username} onChange={(e) => setUsername(e.target.value)}
                 autoComplete="username" />
        </label>
        <label>
          Password
          <input type="password" value={password}
                 onChange={(e) => setPassword(e.target.value)}
                 autoComplete="current-password" />
        </label>
        <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {error && <div className="orgError">{error}</div>}
        <div className="orgSeeds">
          Seeded: <code>sanjeevani</code> · <code>metrocsr</code> ·{" "}
          <code>ddma</code> · <code>hamidia</code>
        </div>
      </form>
    </div>
  );
}

function Dashboard({ session, logout }: { session: OrgSession; logout: () => void }) {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [roster, setRoster] = useState<RosterMember[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [tab, setTab] = useState<"assignments" | "roster">("assignments");

  const refresh = useCallback(async () => {
    const [a, r] = await Promise.all([
      orgFetch("/api/v1/org/assignments", session).then((x) => x.json()),
      orgFetch("/api/v1/org/roster", session).then((x) => x.json()),
    ]);
    setAssignments((a.assignments ?? []) as Assignment[]);
    setRoster((r.roster ?? []) as RosterMember[]);
  }, [session]);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const assign = async (matchId: string, helperId: string) => {
    setBusyId(matchId);
    setNote(null);
    const res = await orgFetch(`/api/v1/org/assignments/${matchId}/assign`, session, {
      method: "POST",
      body: JSON.stringify({ org_id: session.org_id, helper_id: helperId }),
    });
    const j = await res.json();
    setNote(
      j.status === "ok"
        ? `Assigned ${matchId} to ${helperId}. It is now acceptable by that helper.`
        : `Could not assign: ${j.error ?? j.detail ?? res.status}`,
    );
    setBusyId(null);
    await refresh();
  };

  const pending = assignments.filter((a) => a.state === "awaiting_assignment");

  return (
    <div className="admin">
      <header className="topbar">
        <div className="brand">
          <span className="mark">PACT</span>
          <span className="sub">{session.org_name}</span>
        </div>
        <nav className="nav">
          <button className={`navItem ${tab === "assignments" ? "active" : ""}`}
                  onClick={() => setTab("assignments")}>
            Assignments{pending.length ? ` (${pending.length})` : ""}
          </button>
          <button className={`navItem ${tab === "roster" ? "active" : ""}`}
                  onClick={() => setTab("roster")}>
            Roster
          </button>
        </nav>
        <div className="status">
          <span className="groupCode" title="Helpers join your organization with this code">
            {session.group_code}
          </span>
          <button className="navItem" onClick={logout}>Sign out</button>
        </div>
      </header>

      <section className="orgBoundary">
        <span className="pLabel shared">you see</span>
        your own allocations, your roster, the reason each was assigned to you
        <span className="pLabel held">you never see</span>
        other organizations&rsquo; allocations or stock, the cross-organization
        deliberation, or the seeker&rsquo;s identity until your helper accepts
      </section>

      {note && <div className="orgNote">{note}</div>}

      {tab === "assignments" ? (
        assignments.length === 0 ? (
          <div className="empty">
            <h2>No assignments yet</h2>
            <p>Allocations made to {session.org_name} appear here.</p>
          </div>
        ) : (
          <div className="stream">
            {assignments.map((a) => (
              <AssignmentCard key={a.match_id} a={a} roster={roster}
                              busy={busyId === a.match_id} onAssign={assign} />
            ))}
          </div>
        )
      ) : (
        <div className="stream">
          <table className="reqTable">
            <thead>
              <tr><th>Helper</th><th>UID</th><th>Status</th><th>Capabilities</th></tr>
            </thead>
            <tbody>
              {roster.map((m) => (
                <tr key={m.helper_id}>
                  <td>{m.name ?? m.helper_id}</td>
                  <td className="trace">{m.uid}</td>
                  <td className="dimCell">{m.status}</td>
                  <td className="dimCell">{(m.capabilities ?? []).join(", ") || "—"}</td>
                </tr>
              ))}
              {roster.length === 0 && (
                <tr><td colSpan={4} className="dimCell">
                  Nobody has joined with <code>{session.group_code}</code> yet.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AssignmentCard({ a, roster, busy, onAssign }: {
  a: Assignment;
  roster: RosterMember[];
  busy: boolean;
  onAssign: (matchId: string, helperId: string) => void;
}) {
  const [helper, setHelper] = useState(roster[0]?.helper_id ?? "");
  useEffect(() => {
    if (!helper && roster.length) setHelper(roster[0].helper_id);
  }, [roster, helper]);

  const alloc = a.allocation ?? {};
  const awaiting = a.state === "awaiting_assignment";
  const seeker = (a.seeker ?? {}) as {
    lat?: number; lon?: number; need?: string; quantity?: number; urgency?: string;
  };
  // The A7 org projection rounds the position to 2 decimals (~1 km). Earlier
  // this looked for `area`/`loc_masked`/`location_name`, none of which the
  // projection emits, so every card claimed the area was withheld -- which
  // contradicted the boundary banner directly above it.
  const area = seeker.lat != null && seeker.lon != null
    ? `${seeker.lat.toFixed(2)}, ${seeker.lon.toFixed(2)}  (~1 km)`
    : null;

  return (
    <article className={`card ${awaiting ? "awaiting_admin" : ""}`}>
      <div className="cardHead">
        <div>
          <span className="trace">{a.match_id}</span>
          <span className={`badge ${awaiting ? "awaiting_admin" : "committed"}`}>
            {(a.state ?? "").replace(/_/g, " ")}
          </span>
        </div>
        <span className="summary">
          {alloc.qty} × {(alloc.resource ?? "").replace(/_/g, " ")}
          {alloc.eta_min != null ? ` · ETA ${alloc.eta_min} min` : ""}
        </span>
      </div>

      {a.justification && <p className="orgWhy">{a.justification}</p>}

      <div className="orgSeeker">
        <span className="pLabel shared">approximate area</span>
        {area ?? "not reported"}
        {seeker.urgency && <span className="orgUrgency">{seeker.urgency}</span>}
        <span className="pLabel held">exact position &amp; contact</span>
        withheld until your helper accepts
      </div>

      {awaiting ? (
        <div className="gateActions orgAssign">
          <select value={helper} onChange={(e) => setHelper(e.target.value)}>
            {roster.map((m) => (
              <option key={m.helper_id} value={m.helper_id}>
                {m.name ?? m.helper_id}
              </option>
            ))}
          </select>
          <button className="approve" disabled={busy || !helper}
                  onClick={() => onAssign(a.match_id, helper)}>
            {busy ? "Assigning…" : "Assign to helper"}
          </button>
          <span className="simHint">
            Naming a helper is what makes this acceptable by them.
          </span>
        </div>
      ) : (
        <div className="adminNote">
          {a.assigned_helper_id
            ? `Dispatched to ${a.assigned_helper_id}.`
            : "No assignment action needed."}
        </div>
      )}
    </article>
  );
}
