"use client";

import React from "react";
import { LogOut, Bot, Terminal, UserCheck } from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface TopbarProps {
  onToggleDebug?: () => void;
  onToggleAgentOps?: () => void;
}

export default function Topbar({ onToggleDebug, onToggleAgentOps }: TopbarProps) {
  const { data: session } = useSession();
  const user = session?.user;
  const pathname = usePathname();

  const pageMeta = (() => {
    if (pathname.includes("/meetings")) return { section: "Work", title: "Meetings" };
    if (pathname.includes("/forms")) return { section: "Work", title: "Forms" };
    if (pathname.includes("/signatures")) return { section: "Work", title: "Signatures" };
    if (pathname.includes("/contract-assistant")) return { section: "Work", title: "Contracts" };
    if (pathname.includes("/dyslexic")) return { section: "Work", title: "Dyslexic CRM" };
    if (pathname.includes("/members")) return { section: "Governance", title: "Members" };
    if (pathname.includes("/iam")) return { section: "Governance", title: "IAM" };
    if (pathname.includes("/audit")) return { section: "Governance", title: "Audit log" };
    if (pathname.includes("/forks")) return { section: "Network", title: "Forks" };
    if (pathname.includes("/finance")) return { section: "Network", title: "Finance" };
    if (pathname.includes("/settings")) return { section: "Network", title: "Settings" };
    if (pathname.includes("/profile")) return { section: "Overview", title: "Profile" };
    return { section: "Overview", title: "Dashboard" };
  })();

  const displayName = user?.name ?? user?.email?.split("@")[0] ?? "User";
  const initials = displayName
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="sticky top-0 z-20 flex min-h-20 items-center justify-between gap-4 border-b-2 border-black bg-[#f4f1ec] px-4 pl-16 text-[#120f0a] md:px-8">
      <div className="flex min-w-0 items-center gap-4">
        <div className="hidden min-w-0 sm:block">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-burgundy">
            {pageMeta.section} / workspace
          </p>
          <p className="truncate font-heading text-lg font-black leading-tight text-[#120f0a]">
            {pageMeta.title}
          </p>
        </div>

        <Link
          href="/dashboard/dyslexic"
          className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-base border-2 border-[#120f0a] bg-white px-3 text-xs font-mono font-bold text-[#120f0a] transition-colors hover:border-burgundy hover:text-burgundy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
        >
          <span className="flex size-2 rounded-full bg-orange" />
          <span>DYSLEXIC</span>
        </Link>

        {/* AI Agent Ops Quick Trigger */}
        <button
          type="button"
          onClick={onToggleAgentOps}
          className="hidden min-h-10 sm:inline-flex items-center gap-1.5 rounded-base border-2 border-[#120f0a] bg-white px-3 text-xs font-mono font-bold text-[#120f0a] transition-colors hover:border-burgundy hover:text-burgundy"
        >
          <Bot className="size-3.5 text-purple-400" />
          <span>AI AGENTS</span>
          <span className="flex size-1.5 rounded-full bg-purple-400" />
        </button>

        {/* Stats for Nerds Debugger Toggle */}
        <button
          type="button"
          onClick={onToggleDebug}
          className="hidden min-h-10 md:inline-flex items-center gap-1.5 rounded-base border-2 border-[#120f0a] bg-white px-3 text-xs font-mono font-bold text-[#120f0a] transition-colors hover:border-burgundy hover:text-burgundy"
        >
          <Terminal className="size-3.5 text-amber-400" />
          <span>STATS / DEBUG</span>
        </button>
      </div>

      <div className="flex items-center gap-3">
        {/* Avatar & Profile Setup Link */}
        <Link
          href="/dashboard/profile"
          className="flex min-h-11 items-center gap-2.5 rounded-base px-2 transition-colors hover:bg-black/5 group"
          title="Team Profile & Chrono v2 Setup"
        >
          <div className="relative flex size-8 shrink-0 overflow-hidden rounded-base border-2 border-[#120f0a] group-hover:border-burgundy transition-all bg-[#120f0a]">
            {user?.image ? (
              <img
                src={user.image}
                alt={displayName}
                className="aspect-square size-full object-cover"
              />
            ) : (
              <div className="flex size-full items-center justify-center bg-[#120f0a] text-xs font-bold text-white">
                {initials}
              </div>
            )}
          </div>
          <span className="hidden text-xs font-mono font-bold text-[#120f0a] sm:block group-hover:text-burgundy transition-colors">
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
