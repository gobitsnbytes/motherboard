import React from "react";
import { Users } from "lucide-react";
import EmptyState from "../../../components/dashboard/EmptyState";
import { MembersContent } from "components/dashboard/MembersContent";

export const metadata = {
  title: "Members — bits&bytes Motherboard",
};

export default function MembersPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="border-b-2 border-[#120f0a] pb-5">
        <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-burgundy">Governance / directory</p>
        <h1 className="text-3xl font-heading font-bold text-foreground sm:text-4xl">
          Members
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1 max-w-2xl">
          Review who has access, how they joined, and which operational groups they belong to.
        </p>
      </div>

      <MembersContent />
    </div>
  );
}
