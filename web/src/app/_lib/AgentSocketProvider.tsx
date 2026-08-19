"use client";

// One socket for the whole admin portal, shared through context.
//
// Without this, every route mounts its own useAgentSocket: a second WebSocket
// opens, and the new page starts from empty state -- so "All Requests" would
// only ever show events that arrived after you navigated to it. Runs must
// outlive navigation.

import { createContext, useContext, type ReactNode } from "react";
import { useAgentSocket } from "./useAgentSocket";

type SocketValue = ReturnType<typeof useAgentSocket>;

const Ctx = createContext<SocketValue | null>(null);

export function AgentSocketProvider({ children }: { children: ReactNode }) {
  const value = useAgentSocket();
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAgents(): SocketValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAgents must be used inside <AgentSocketProvider>");
  return v;
}
