"use client";

import React from "react";
import { LogOut } from "lucide-react";
import { signOut, useSession } from "next-auth/react";

export default function Topbar() {
  const { data: session } = useSession();
  const user = session?.user;

  const displayName = user?.name ?? user?.email?.split("@")[0] ?? "User";
  const initials = displayName
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="sticky top-0 z-10 flex min-h-16 items-center justify-between border-b-2 border-[#5b0f1a] bg-[#3c0a12] px-4 text-white md:px-8">
      <div>
        <p className="font-heading text-[10px] font-bold uppercase tracking-[0.2em] text-[#fc920d]">bits&bytes™</p>
        <p className="mt-0.5 text-xs text-white/60">Operations network · 30 city forks</p>
      </div>
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="relative flex size-8 shrink-0 overflow-hidden rounded-full border-2 border-border">
          {user?.image ? (
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
        <span className="hidden text-sm font-semibold text-white sm:block">
          {displayName}
        </span>
        <button
          type="button"
          onClick={() => {
            signOut({ callbackUrl: "/login" });
          }}
          className="inline-flex items-center justify-center gap-1.5 rounded-base border-2 border-[#fc920d] bg-[#fc920d] px-3 py-1.5 text-xs font-bold text-[#120f0a] shadow-[2px_2px_0_#120f0a] transition-transform hover:translate-x-0.5 hover:translate-y-0.5 hover:shadow-none"
        >
          <LogOut className="size-3.5" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}
