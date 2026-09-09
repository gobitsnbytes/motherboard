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
  return (
    <div className="min-h-screen bg-[#1e0509] text-white selection:bg-[#fc920d] selection:text-[#120f0a]">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col md:ml-64">
        <Topbar />
        <main className="flex-1 overflow-auto bg-[#f8f1e7] p-4 text-[#120f0a] md:p-8">{children}</main>
      </div>
    </div>
  );
}
