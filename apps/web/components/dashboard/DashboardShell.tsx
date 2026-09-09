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
      <div className="flex min-w-0 flex-1 flex-col md:ml-72">
        <Topbar
          onToggleDebug={() => setDebugOpen((prev) => !prev)}
          onToggleAgentOps={() => setAgentOpsOpen((prev) => !prev)}
        />
        <main className="motherboard-canvas flex flex-1 flex-col justify-between overflow-auto px-4 py-6 sm:px-8 sm:py-8 lg:px-10">
          <div className="mx-auto flex w-full max-w-[1480px] flex-1">{children}</div>
          <DashboardFooter />
        </main>
      </div>

      <CockpitDebugger isOpen={debugOpen} onClose={() => setDebugOpen(false)} />
      <AgentOpsDrawer isOpen={agentOpsOpen} onClose={() => setAgentOpsOpen(false)} />
    </div>
  );
}

