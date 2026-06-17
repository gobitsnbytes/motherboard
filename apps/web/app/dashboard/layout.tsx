import React from "react";
import { redirect } from "next/navigation";
import { auth } from "../../lib/auth";
import AuthProvider from "../../components/dashboard/AuthProvider";
import DashboardShell from "../../components/dashboard/DashboardShell";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) {
    redirect("/login");
  }

  return (
    <AuthProvider>
      <DashboardShell>{children}</DashboardShell>
    </AuthProvider>
  );
}
