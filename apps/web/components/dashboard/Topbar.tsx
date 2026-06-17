"use client";

import React from "react";
import { LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

// TODO: Replace with real session data from backend auth
const MOCK_USER = {
  name: "Akshat",
  email: "akshat@gobitsnbytes.org",
  image: null,
};

export default function Topbar() {
  const user = MOCK_USER;

  const displayName = user.name ?? user.email?.split("@")[0] ?? "User";
  const initials = displayName
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-end border-b-2 border-border bg-[#111] px-4 md:px-6">
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="relative flex size-8 shrink-0 overflow-hidden rounded-full border-2 border-border">
          {user.image ? (
            <img
              src={user.image}
              alt={displayName}
              className="aspect-square size-full"
            />
          ) : (
            <div className="flex size-full items-center justify-center rounded-full bg-secondary-background text-xs font-bold text-foreground">
              {initials}
            </div>
          )}
        </div>
        <span className="hidden text-sm font-medium text-foreground sm:block">
          {displayName}
        </span>
        <button
          type="button"
          onClick={() => {
            signOut({ callbackUrl: "/login" });
          }}
          className="inline-flex items-center justify-center gap-1.5 rounded-base border-2 border-border bg-main px-3 py-1.5 text-xs font-medium text-main-foreground transition-all hover:translate-x-boxShadowX hover:translate-y-boxShadowY hover:shadow-none shadow-shadow"
        >
          <LogOut className="size-3.5" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}
