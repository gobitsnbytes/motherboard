import React from "react";
import { LayoutDashboard } from "lucide-react";
import EmptyState from "../../../components/dashboard/EmptyState";
import StatCard from "components/dashboard/StatCard";
import { OverviewContent } from "components/dashboard/OverviewContent";

export const metadata = {
  title: "Overview — bits&bytes Motherboard",
};

export default function OverviewPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="border-b-2 border-[#120f0a] pb-5">
        <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-burgundy">Operations / overview</p>
        <h1 className="text-3xl font-heading font-bold text-foreground sm:text-4xl">
          Overview
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1">
          Dashboard home — organization health at a glance.
        </p>
      </div>

      <OverviewContent />
    </div>
  );
}
