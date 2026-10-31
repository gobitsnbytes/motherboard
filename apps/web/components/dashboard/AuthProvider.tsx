"use client";

import { SessionProvider } from "next-auth/react";

// The JWT lasts 30 days; refetching on every tab focus only adds a serverless call.
export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SessionProvider refetchOnWindowFocus={false}>{children}</SessionProvider>;
}
