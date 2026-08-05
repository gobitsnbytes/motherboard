
import React from "react";
import IAMHierarchyVisualizer from "../../../components/dashboard/IAMHierarchyVisualizer";
import IAMRoleMappings from "../../../components/dashboard/IAMRoleMappings";

export const metadata = {
  title: "IAM & Hierarchy — bits&bytes Motherboard",
};

export default function IAMPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Identity & Access Management
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1">
          Visual role hierarchy, permission policies, and 2-way Discord role sync.
        </p>
      </div>

      <IAMHierarchyVisualizer />
      <IAMRoleMappings />
    </div>
  );
}
