import type { ReactNode } from "react";
import { AgentSocketProvider } from "../_lib/AgentSocketProvider";

// Wraps every /admin route so the deliberation stream survives navigation
// between Live Matches and All Requests.
export default function AdminLayout({ children }: { children: ReactNode }) {
  return <AgentSocketProvider>{children}</AgentSocketProvider>;
}
