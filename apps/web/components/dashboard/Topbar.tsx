"use client";

import React from "react";
import { LogOut, Bot, Terminal, UserCheck } from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import Link from "next/link";

interface TopbarProps {
  onToggleDebug?: () => void;
  onToggleAgentOps?: () => void;
}

export default function Topbar({ onToggleDebug, onToggleAgentOps }: TopbarProps) {
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
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b-2 border-border bg-[#111] px-4 md:px-6">
      <div className="flex items-center gap-2">
        <Link
          href="/dashboard/dyslexic"
          className="inline-flex items-center gap-2 rounded-base border-2 border-border bg-main/10 px-3 py-1 text-xs font-bold text-foreground transition-all hover:bg-main hover:text-main-foreground"
        >
          <span className="flex size-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Dyslexic</span>
        </Link>

        {/* AI Agent Ops Quick Trigger */}
        <button
          type="button"
          onClick={onToggleAgentOps}
          className="hidden sm:inline-flex items-center gap-1.5 rounded-base border border-purple-500/40 bg-purple-500/10 px-2.5 py-1 text-xs font-bold text-purple-300 transition-all hover:bg-purple-500/20"
        >
          <Bot className="size-3.5 text-purple-400" />
          <span>AI Agents</span>
          <span className="flex size-1.5 rounded-full bg-purple-400" />
        </button>

        {/* Stats for Nerds Debugger Toggle */}
        <button
          type="button"
          onClick={onToggleDebug}
          className="hidden md:inline-flex items-center gap-1.5 rounded-base border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs font-bold text-amber-300 transition-all hover:bg-amber-500/20"
        >
          <Terminal className="size-3.5 text-amber-400" />
          <span>Stats / Debug</span>
        </button>
      </div>

      <div className="flex items-center gap-3">
        {/* Avatar & Profile Setup Link */}
        <Link
          href="/dashboard/profile"
          className="flex items-center gap-2.5 rounded-base p-1 hover:bg-white/5 transition-all group"
          title="Team Profile & Chrono v2 Setup"
        >
          <div className="relative flex size-8 shrink-0 overflow-hidden rounded-full border-2 border-border group-hover:border-amber-400 transition-all">
            {user?.image ? (
              <img
                src={user.image}
                alt={displayName}
                className="aspect-square size-full object-cover"
              />
            ) : (
              <div className="flex size-full items-center justify-center rounded-full bg-secondary-background text-xs font-bold text-foreground">
                {initials}
              </div>
            )}
          </div>
          <span className="hidden text-sm font-medium text-foreground sm:block group-hover:text-amber-400 transition-colors">
            {displayName}
          </span>
        </Link>

        {/* Clean Sign Out */}
        <button
          type="button"
          onClick={() => {
            signOut({ callbackUrl: "/login", redirect: true });
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
