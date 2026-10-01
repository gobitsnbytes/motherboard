"use client";
import { hasAccess } from "../../lib/access";
import { useAccess } from "./AccessProvider";

export default function AccessGate({ permission, children }: { permission: string; children: React.ReactNode }) {
  const { access } = useAccess();
  return hasAccess(access, permission) ? children : null;
}
