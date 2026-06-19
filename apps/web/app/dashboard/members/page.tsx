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
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Members
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1">
          Manage organization members and their Discord-linked accounts.
        </p>
      </div>

      <MembersContent />
    </div>
  );
}