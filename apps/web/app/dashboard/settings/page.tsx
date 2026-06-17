import React from "react";
import { Settings } from "lucide-react";
import EmptyState from "../../../components/dashboard/EmptyState";

export const metadata = {
  title: "Settings — bits&bytes Motherboard",
};

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Settings
        </h1>
        <p className="text-sm text-muted-foreground font-base mt-1">
          Organization configuration and preferences.
        </p>
      </div>
      <EmptyState
        icon={<Settings className="size-6" />}
        title="Settings Coming Soon"
        description="This page will allow configuring organization-wide settings, Discord guild sync preferences, and notification rules."
      />
    </div>
  );
}
