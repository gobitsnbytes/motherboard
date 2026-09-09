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
    <header className="sticky top-0 z-20 flex min-h-20 items-center justify-between border-b-2 border-zinc-700 bg-[#111115] px-4 md:px-8">
      <div className="flex items-center gap-2.5">
        <Link
          href="/dashboard/dyslexic"
          className="inline-flex min-h-11 items-center gap-2 rounded-base border-2 border-zinc-600 px-3 text-xs font-mono font-bold text-white transition-colors hover:border-orange hover:text-orange focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
        >
          <span className="flex size-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>DYSLEXIC</span>
        </Link>

        {/* AI Agent Ops Quick Trigger */}
        <button
          type="button"
          onClick={onToggleAgentOps}
          className="hidden min-h-10 sm:inline-flex items-center gap-1.5 rounded-base border-2 border-zinc-600 px-3 text-xs font-mono font-bold text-purple-200 transition-colors hover:border-purple-400"
        >
          <Bot className="size-3.5 text-purple-400" />
          <span>AI AGENTS</span>
          <span className="flex size-1.5 rounded-full bg-purple-400" />
        </button>

        {/* Stats for Nerds Debugger Toggle */}
        <button
          type="button"
          onClick={onToggleDebug}
          className="hidden min-h-10 md:inline-flex items-center gap-1.5 rounded-base border-2 border-zinc-600 px-3 text-xs font-mono font-bold text-amber-200 transition-colors hover:border-amber-400"
        >
          <Terminal className="size-3.5 text-amber-400" />
          <span>STATS / DEBUG</span>
        </button>
      </div>

      <div className="flex items-center gap-3">
        {/* Avatar & Profile Setup Link */}
        <Link
          href="/dashboard/profile"
          className="flex min-h-11 items-center gap-2.5 rounded-base px-1 transition-colors hover:bg-white/5 group"
          title="Team Profile & Chrono v2 Setup"
        >
          <div className="relative flex size-8 shrink-0 overflow-hidden rounded-base border-2 border-border group-hover:border-orange transition-all bg-black">
            {user?.image ? (
              <img
                src={user.image}
                alt={displayName}
                className="aspect-square size-full object-cover"
              />
            ) : (
              <div className="flex size-full items-center justify-center bg-black text-xs font-bold text-white">
                {initials}
              </div>
            )}
          </div>
          <span className="hidden text-xs font-mono font-bold text-white sm:block group-hover:text-orange transition-colors">
            {displayName}
          </span>
        </Link>

        {/* Clean Sign Out */}
        <button
          type="button"
          onClick={() => {
            signOut({ callbackUrl: "/login", redirect: true });
          }}
          className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-base border-2 border-black bg-burgundy px-3.5 text-xs font-heading font-black uppercase tracking-wider text-white shadow-light transition-transform active:translate-x-[2px] active:translate-y-[2px] active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
        >
          <LogOut className="size-3.5" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}
