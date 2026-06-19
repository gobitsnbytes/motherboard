import React from "react";
import { AuditContent } from "../../../components/dashboard/AuditContent";

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

      <AuditContent />
    </div>
  );
}