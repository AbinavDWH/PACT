"use client";

import { useEffect, useState } from "react";
import { listPlans } from "../../lib/api";
import { Plan } from "../../lib/types";
import AgentLog from "../../components/AgentLog";

const statusColor = (s: string) => {
  if (s === "delivered") return "bg-green-100 text-green-700";
  if (s === "ready_for_dispatch") return "bg-blue-100 text-blue-700";
  if (s === "partial") return "bg-yellow-100 text-yellow-700";
  if (s === "no_suppliers") return "bg-red-100 text-red-700";
  return "bg-[#FFF2DB] text-[#7c4a12]";
};

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await listPlans();
        if (!mounted) return;
        setPlans(res.plans);
        setError(null);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Backend unreachable");
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const delivered = plans.filter((p) => p.status === "delivered").length;
  const ready = plans.filter((p) => ["ready_for_dispatch", "partial"].includes(p.status)).length;
  const noSuppliers = plans.filter((p) => p.status === "no_suppliers").length;

  return (
    <main className="min-h-screen bg-[#FFFAF3] px-6 py-8 text-[#2b1a0e]">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F62440]">
            Allocation Plans
          </p>
          <h1 className="mt-1 text-3xl font-bold">Dispatch & Delivery</h1>
          <p className="mt-1 text-sm text-[#7c6a58]">
            Coordination Agent plans with dispatch lifecycle tracking.
          </p>
        </header>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach the FastAPI backend ({error}). Start it with{" "}
            <code>uvicorn app.main:app --reload --host 0.0.0.0</code>.
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#2b1a0e]">{plans.length}</div>
            <div className="text-sm text-[#7c6a58]">Total Plans</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#4CAF50]">{delivered}</div>
            <div className="text-sm text-[#7c6a58]">Delivered</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#2196F3]">{ready}</div>
            <div className="text-sm text-[#7c6a58]">Ready / Partial</div>
          </div>
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6">
            <div className="text-3xl font-bold text-[#F62440]">{noSuppliers}</div>
            <div className="text-sm text-[#7c6a58]">No Suppliers</div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-4">
            {plans.length === 0 ? (
              <div className="rounded-xl border border-[#FFE5BF] bg-white p-8 text-center text-[#a1866f]">
                No allocation plans created yet. Accept a need request to trigger the Coordination Agent.
              </div>
            ) : (
              plans.map((plan) => {
                const coverage =
                  plan.required_quantity > 0
                    ? Math.round((plan.allocated_quantity / plan.required_quantity) * 100)
                    : 0;
                return (
                  <div key={plan.plan_id} className="rounded-xl border border-[#FFE5BF] bg-white p-6">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="text-lg font-bold">{plan.plan_id}</h3>
                        <p className="text-sm text-[#7c6a58]">
                          {plan.resource} → {plan.location_name ?? plan.location_code}
                        </p>
                      </div>
                      <span className={`rounded-lg px-3 py-1 text-sm font-semibold ${statusColor(plan.status)}`}>
                        {plan.status}
                      </span>
                    </div>

                    {(plan as any).ai_summary && (
                      <div className="mt-3 rounded-lg border border-[#FFE5BF] bg-[#FFFAF3] px-3 py-2 text-xs text-[#4a3a28]">
                        <div><span className="font-bold text-[#F62440]">AI Dispatch Briefing: </span>{(plan as any).ai_summary}</div>
                        {(plan as any).ai_risks && (
                          <div className="mt-1"><span className="font-bold text-[#FF9800]">Risks: </span>{(plan as any).ai_risks}</div>
                        )}
                      </div>
                    )}

                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                      <div>
                        <div className="text-xs text-[#a1866f]">Required</div>
                        <div className="text-lg font-semibold">{plan.required_quantity}</div>
                      </div>
                      <div>
                        <div className="text-xs text-[#a1866f]">Allocated</div>
                        <div className="text-lg font-semibold">{plan.allocated_quantity}</div>
                      </div>
                      <div>
                        <div className="text-xs text-[#a1866f]">Coverage</div>
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 overflow-hidden rounded-full bg-[#FFF2DB]">
                            <div className="h-full bg-[#F62440]" style={{ width: `${coverage}%` }} />
                          </div>
                          <span className="text-lg font-semibold">{coverage}%</span>
                        </div>
                      </div>
                    </div>

                    {plan.allocations.length > 0 && (
                      <div className="mt-4">
                        <div className="text-xs font-semibold uppercase text-[#7c4a12]">Allocations</div>
                        <div className="mt-2 space-y-2">
                          {plan.allocations.map((alloc, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between rounded-lg bg-[#FFFAF3] px-3 py-2 text-sm"
                            >
                              <span className="font-medium">{alloc.organization_id}</span>
                              <div className="flex gap-4">
                                <span className="font-mono">{alloc.quantity} units</span>
                                <span className="text-[#a1866f]">ETA: {alloc.eta_hours}h</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          <AgentLog />
        </div>
      </div>
    </main>
  );
}