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
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
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
