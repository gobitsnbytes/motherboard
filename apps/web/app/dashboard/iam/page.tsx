import React from "react";
import { Shield } from "lucide-react";
import EmptyState from "../../../components/dashboard/EmptyState";

export const metadata = {
  title: "IAM — bits&bytes Motherboard",
};

export default function IAMPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Identity &amp; Access Management
        </h1>
        <p className="text-sm text-muted-foreground font-base mt-1">
          Configure role mappings, permissions, and delegation policies.
        </p>
      </div>
      <EmptyState
        icon={<Shield className="size-6" />}
        title="IAM Configuration Coming Soon"
        description="This page will allow managing role-to-permission mappings, delegation chains, and access policies once the IAM engine is live."
      />
    </div>
  );
}
