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
    <div className="motherboard-shell flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col md:ml-64">
        <Topbar
          onToggleDebug={() => setDebugOpen((prev) => !prev)}
          onToggleAgentOps={() => setAgentOpsOpen((prev) => !prev)}
        />
        <main className="motherboard-canvas flex flex-1 flex-col justify-between overflow-auto p-4 sm:p-6 lg:p-8">
          <div className="flex-1">{children}</div>
          <DashboardFooter />
        </main>
      </div>

      <CockpitDebugger isOpen={debugOpen} onClose={() => setDebugOpen(false)} />
      <AgentOpsDrawer isOpen={agentOpsOpen} onClose={() => setAgentOpsOpen(false)} />
    </div>
  );
}

