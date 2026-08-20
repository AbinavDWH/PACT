"use client";

// Where the console gets its facts instead of hardcoding them.
//
// Two values used to be literals in the page:
//
//   NEEDS = ["medical_kits", "water_kits", "food_kits", "tents", "rescue_team"]
//   location_name: "Region A"
//
// Both were wrong in a way that was invisible. The database holds nine
// resources, not five, and the request carried no coordinates at all -- so the
// pipeline fell back to its built-in default centre (Bhopal). With the fixtures
// seeded in Chennai, every offer sat ~1100 km outside the 150 km radius ladder,
// `$geoNear` returned nothing, and the run completed on hardcoded candidates
// with `geo_live: false`. A committed allocation appeared either way.
//
// So the resource list comes from GET /admin/inventory and the position comes
// from GET /admin/seed, and the request the portal sends actually exercises the
// one real database query in the system.

import { useCallback, useEffect, useState } from "react";
import { authFetch } from "./useAgentSocket";

export interface InventoryItem {
  resource: string;
  available: number;
  offers: number;
}

export interface Anchor {
  lat: number;
  lon: number;
}

export interface ConsoleMeta {
  inventory: InventoryItem[];
  anchor: Anchor | null;
  radiusLadderKm: number[];
  /** True when Groq is configured; false means deterministic fallbacks only. */
  liveAgents: boolean;
  mongoConnected: boolean;
  autopilot: boolean;
  gateTimeoutS: number | null;
  loading: boolean;
  /** Set when the backend could not be reached at all. */
  error: string | null;
  refresh: () => Promise<void>;
}

export function useConsoleMeta(): ConsoleMeta {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const [radiusLadderKm, setRadius] = useState<number[]>([]);
  const [liveAgents, setLiveAgents] = useState(false);
  const [mongoConnected, setMongo] = useState(false);
  const [autopilot, setAutopilot] = useState(false);
  const [gateTimeoutS, setGateTimeout] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // `alive` is threaded through so a resolve arriving after unmount does not
  // write to a dead component. The fetch itself is declared here rather than as
  // a useCallback invoked from an effect: calling a setState-bearing callback
  // straight from an effect body is the cascading-render pattern React 19 warns
  // about, and it is also how a stale response ends up overwriting a newer one.
  const run = useCallback(async (alive: () => boolean) => {
    try {
      const [inv, seed, stats] = await Promise.all([
        authFetch("/api/v1/admin/inventory").then((r) => r.json()),
        authFetch("/api/v1/admin/seed").then((r) => r.json()),
        authFetch("/api/v1/admin/stats").then((r) => r.json()),
      ]);
      if (!alive()) return;
      setInventory((inv.resources ?? []) as InventoryItem[]);
      // `centre` is null before the fixtures are seeded. Falling back to
      // `default` would send a position no offer is near, which is the exact
      // failure this hook exists to stop -- so it stays null and the page says
      // so rather than dispatching into nothing.
      setAnchor(seed.centre ?? null);
      setRadius((seed.radius_ladder_km ?? []) as number[]);
      setLiveAgents(Boolean(stats.groq));
      setMongo(Boolean(stats.mongo_connected));
      setAutopilot(Boolean(stats.autopilot));
      setGateTimeout(
        typeof stats.gate_timeout_s === "number" ? stats.gate_timeout_s : null,
      );
      setError(null);
    } catch {
      if (alive()) setError("UNREACHABLE");
    } finally {
      if (alive()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    // The rule below cannot see that every setState in `run` happens after an
    // await, i.e. in a promise continuation rather than synchronously during
    // the effect -- which is exactly the pattern it asks for. There is no
    // cascading render here; the guard above already prevents a write after
    // unmount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void run(() => alive);
    return () => { alive = false; };
  }, [run]);

  // Exposed for the retry affordance. Always live, since it is user-initiated.
  const refresh = useCallback(() => run(() => true), [run]);

  return {
    inventory, anchor, radiusLadderKm, liveAgents, mongoConnected,
    autopilot, gateTimeoutS, loading, error, refresh,
  };
}
