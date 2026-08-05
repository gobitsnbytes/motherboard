"use client";

import React, { useState } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import DashboardFooter from "./DashboardFooter";
import CockpitDebugger from "./CockpitDebugger";
import AgentOpsDrawer from "./AgentOpsDrawer";

export default function DashboardShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const [debugOpen, setDebugOpen] = useState(false);
  const [agentOpsOpen, setAgentOpsOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#0a0a0a]">
      <Sidebar />
      <div className="flex flex-1 flex-col md:ml-64">
        <Topbar
          onToggleDebug={() => setDebugOpen((prev) => !prev)}
          onToggleAgentOps={() => setAgentOpsOpen((prev) => !prev)}
        />
        <main className="flex flex-1 flex-col justify-between overflow-auto p-4 md:p-6">
          <div className="flex-1">{children}</div>
          <DashboardFooter />
        </main>
      </div>

      <CockpitDebugger isOpen={debugOpen} onClose={() => setDebugOpen(false)} />
      <AgentOpsDrawer isOpen={agentOpsOpen} onClose={() => setAgentOpsOpen(false)} />
    </div>
  );
}

