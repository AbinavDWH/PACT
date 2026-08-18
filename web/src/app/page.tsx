"use client";

import { FormEvent, useMemo, useState } from "react";
import "./page.css";

type Resource = "food_kits" | "water_kits" | "medical_kits" | "tents";
type Allocation = { organization: string; resource: Resource; quantity: number; eta: string; region: string; status: string };
type ApiPlan = { plan_id: string; unmet_quantity: number; allocations: { organization_id: string; resource: Resource; quantity: number; eta_hours: number; approximate_service_region: string; status: string }[]; activity: string[] };
type CrisisResponse = { status: string; plan: ApiPlan };

const resources: Record<Resource, string> = { food_kits: "Food kits", water_kits: "Water kits", medical_kits: "Medical kits", tents: "Emergency tents" };
const inventory: Record<Resource, { organization: string; available: number; eta: string }[]> = {
  food_kits: [{ organization: "CSR_002", available: 220, eta: "4h" }, { organization: "GOV_003", available: 180, eta: "6h" }],
  water_kits: [{ organization: "NGO_001", available: 260, eta: "3h" }, { organization: "CSR_002", available: 150, eta: "5h" }],
  medical_kits: [{ organization: "NGO_001", available: 150, eta: "3h" }, { organization: "HOSP_004", available: 200, eta: "5h" }],
  tents: [{ organization: "GOV_003", available: 120, eta: "6h" }, { organization: "CSR_002", available: 90, eta: "5h" }],
};
const initialAllocations: Allocation[] = [
  { organization: "NGO_001", resource: "medical_kits", quantity: 150, eta: "3h", region: "Region A", status: "Assigned" },
  { organization: "HOSP_004", resource: "medical_kits", quantity: 150, eta: "5h", region: "Region A", status: "Assigned" },
];
const initialActivity = ["Need Assessment Agent classified Region A as critical.", "Privacy Filter withheld 6 sensitive operational fields.", "Matching Agent found two reachable medical-kit providers.", "Coordination Agent prepared PLAN-101 for dispatch."];

export default function Home() {
  const [location, setLocation] = useState("Region A");
  const [resource, setResource] = useState<Resource>("medical_kits");
  const [quantity, setQuantity] = useState(300);
  const [urgency, setUrgency] = useState("Critical");
  const [allocations, setAllocations] = useState<Allocation[]>(initialAllocations);
  const [activity, setActivity] = useState(initialActivity);
  const [planId, setPlanId] = useState("PLAN-101");
  const [notice, setNotice] = useState("Live scenario loaded - ready for a crisis report.");
  const totalAllocated = useMemo(() => allocations.reduce((sum, item) => sum + item.quantity, 0), [allocations]);

  async function submitNeed(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/crises`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ location, resource, quantity, urgency }),
      });
      if (response.ok) {
        const data = await response.json() as CrisisResponse;
        const apiPlan = data.plan;
        setPlanId(apiPlan.plan_id);
        setAllocations(apiPlan.allocations.map((item) => ({ organization: item.organization_id, resource: item.resource, quantity: item.quantity, eta: `${item.eta_hours}h`, region: item.approximate_service_region, status: "Assigned" })));
        setActivity(apiPlan.activity);
        setNotice(apiPlan.unmet_quantity > 0 ? `Partial coverage: ${apiPlan.unmet_quantity} units remain unmet.` : "Response plan generated and ready for dispatch.");
        return;
      }
    } catch {
      // The browser fallback keeps the interface usable when the API is not running.
    }
    let remaining = Math.max(1, quantity);
    const plan = inventory[resource].map((provider) => {
      const assigned = Math.min(provider.available, remaining);
      remaining -= assigned;
      return { organization: provider.organization, resource, quantity: assigned, eta: provider.eta, region: location, status: assigned > 0 ? "Assigned" : "Standby" };
    }).filter((item) => item.quantity > 0);
    const nextPlan = `PLAN-${Math.floor(100 + Math.random() * 900)}`;
    setPlanId(nextPlan); setAllocations(plan);
    setActivity([
      `Need Assessment Agent recorded ${quantity} ${resources[resource].toLowerCase()} for ${location}.`,
      "Privacy Filter shared only capability, ETA, and approximate service region.",
      `Matching Agent ranked ${plan.length} providers by availability and response time.`,
      `Coordination Agent generated ${nextPlan} with ${Math.max(0, quantity - remaining)} kits assigned.`,
      ...(remaining > 0 ? [`Coverage gap: ${remaining} ${resources[resource].toLowerCase()} still required.`] : []),
    ]);
    setNotice(remaining > 0 ? `Partial coverage: ${remaining} units remain unmet.` : "Response plan generated and ready for dispatch.");
  }

  return <main className="shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">✦</span><span>AID GRID</span></div><div className="mission"><span className="pulse" /> Humanitarian coordination command</div><div className="mode">Evaluation 01 <span>•</span> Demo environment</div></header>
    <section className="situation-strip" aria-label="Current situation"><div><span className="eyebrow">Active incident</span><strong>Flood response / Region A</strong></div><div><span className="eyebrow">Coordination state</span><strong className="critical">Critical</strong></div><div><span className="eyebrow">Participating agents</span><strong>04 online</strong></div><div className="strip-note">Selective sharing enabled <span>↗</span></div></section>
    <div className="workspace">
      <section className="intro"><p className="eyebrow">Command decision board</p><h1>Coordinate aid.<br /><em>Keep trust intact.</em></h1><p className="lede">Turn a field need into a transparent allocation plan without exposing donor data, staff records, exact warehouse locations, or internal inventories.</p></section>
      <section className="signal-card" aria-label="System status"><div className="signal-orbit"><span>01</span></div><div><p className="eyebrow">System signal</p><strong>Coordination ready</strong><p>3 response organizations can serve the active crisis zone.</p></div></section>
      <section className="panel report-panel"><div className="panel-title"><div><p className="eyebrow">01 / Field intake</p><h2>Report an urgent need</h2></div><span className="tag">WEB</span></div><form onSubmit={submitNeed}><label>Approximate area<input value={location} onChange={(e) => setLocation(e.target.value)} required /></label><div className="form-grid"><label>Resource<select value={resource} onChange={(e) => setResource(e.target.value as Resource)}>{Object.entries(resources).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Required quantity<input type="number" min="1" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} required /></label></div><label>Urgency<select value={urgency} onChange={(e) => setUrgency(e.target.value)}><option>Critical</option><option>High</option><option>Medium</option></select></label><button type="submit">Assess and coordinate <span>→</span></button></form><p className="form-note">Reports are converted into minimum-necessary coordination data before matching.</p></section>
      <section className="panel allocation-panel"><div className="panel-title"><div><p className="eyebrow">02 / Response plan</p><h2>{planId}</h2></div><span className="ready">Ready for dispatch</span></div><p className="notice">{notice}</p><div className="allocation-table"><div className="row header"><span>Organization</span><span>Allocation</span><span>ETA</span><span>Status</span></div>{allocations.map((item) => <div className="row" key={`${item.organization}-${item.resource}`}><strong>{item.organization}</strong><span>{item.quantity} {resources[item.resource]}</span><span>{item.eta}</span><span className="assigned">{item.status}</span></div>)}</div><div className="plan-summary"><span>Committed now</span><strong>{totalAllocated} units</strong><span>for {allocations[0]?.region ?? location}</span></div></section>
      <section className="panel activity-panel"><div className="panel-title"><div><p className="eyebrow">Decision trace</p><h2>Agent activity</h2></div><span className="tag">LIVE</span></div><ol className="activity-list">{activity.map((event, index) => <li key={`${event}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><p>{event}</p></li>)}</ol></section>
      <section className="panel privacy-panel"><div className="panel-title"><div><p className="eyebrow">Trust boundary</p><h2>Privacy by design</h2></div><span className="shield">◈</span></div><div className="privacy-columns"><div><h3>Shared to coordinate</h3><ul><li>Resource type and quantity</li><li>Approximate service area</li><li>Capacity and response ETA</li></ul></div><div className="hidden"><h3>Kept within each organization</h3><ul><li>Donor and funding details</li><li>Staff and beneficiary data</li><li>Exact warehouse and route data</li></ul></div></div><p className="privacy-foot">The allocation is explainable without requiring an organization to reveal its full operating picture.</p></section>
    </div>
  </main>;
}
