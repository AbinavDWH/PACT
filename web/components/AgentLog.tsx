"use client";

import { useEffect, useState } from "react";
import { listActivity } from "../lib/api";
import { ActivityEntry } from "../lib/types";

export default function AgentLog() {
  const [activity, setActivity] = useState<ActivityEntry[]>([]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await listActivity(50);
        if (mounted) setActivity(res.activity);
      } catch {
        // ignore
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="rounded-xl border border-[#FFE5BF] bg-white">
      <div className="border-b border-[#FFE5BF] bg-[#FFF2DB] px-4 py-3">
        <h3 className="text-sm font-bold uppercase tracking-wide text-[#7c4a12]">
          Agent Activity Feed
        </h3>
      </div>
      <div className="max-h-[400px] overflow-y-auto px-4 py-3">
        {activity.length === 0 ? (
          <p className="text-sm text-[#a1866f]">No agent activity yet.</p>
        ) : (
          <ul className="space-y-3">
            {activity.map((entry, i) => (
              <li key={`${entry.ts}-${i}`} className="text-xs leading-relaxed">
                <div className="font-mono text-[10px] text-[#a1866f]">
                  {new Date(entry.ts).toLocaleTimeString()}
                </div>
                <div>
                  <span className="font-semibold text-[#F62440]">{entry.agent}</span>{" "}
                  <span className="text-[#4a3a28]">{entry.message}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}