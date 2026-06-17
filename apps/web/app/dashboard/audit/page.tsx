import React from "react";
import { ScrollText } from "lucide-react";
import EmptyState from "../../../components/dashboard/EmptyState";

export const metadata = {
  title: "Audit Log — bits&bytes Motherboard",
};

export default function AuditPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Audit Log
        </h1>
        <p className="text-sm text-muted-foreground font-base mt-1">
          Track all administrative actions and system events.
        </p>
      </div>
      <EmptyState
        icon={<ScrollText className="size-6" />}
        title="Audit Log Coming Soon"
        description="This page will display a searchable, filterable log of all administrative actions, permission changes, and system events."
      />
    </div>
  );
}
