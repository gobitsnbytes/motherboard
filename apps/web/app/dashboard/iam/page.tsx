
import React from "react";
import IAMHierarchyVisualizer from "../../../components/dashboard/IAMHierarchyVisualizer";
import { IAMContent } from "../../../components/dashboard/IAMContent";
import IAMRoleMappings from "../../../components/dashboard/IAMRoleMappings";

export const metadata = {
  title: "IAM & Hierarchy — bits&bytes Motherboard",
};

export default function IAMPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="border-b-2 border-[#120f0a] pb-5">
        <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-burgundy">Governance / access</p>
        <h1 className="text-3xl font-heading font-bold text-foreground sm:text-4xl">
          Identity & Access Management
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1 max-w-2xl">
          Decide who can do what, at global or city scope, and keep Discord role mappings explicit.
        </p>
      </div>

      <IAMContent />
      <IAMHierarchyVisualizer />
      <IAMRoleMappings />
    </div>
  );
}
