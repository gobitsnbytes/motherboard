import React from "react";
import DashboardShell from "../../components/dashboard/DashboardShell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // TODO: Wire up real auth session check when backend is ready
  return <DashboardShell>{children}</DashboardShell>;
}
