"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { STAGE_LABELS, stageVariant, type CompanyStage } from "lib/dyslexic";
import type { StreamStatus } from "hooks/useDyslexicStream";

const TABS = [
  { label: "Dashboard", href: "/dashboard/dyslexic" },
  { label: "Companies", href: "/dashboard/dyslexic/companies" },
  { label: "Contacts", href: "/dashboard/dyslexic/contacts" },
  { label: "Leaderboard", href: "/dashboard/dyslexic/leaderboard" },
];

/** Section navigation, styled to match the sidebar's active treatment. */
export function DyslexicTabs() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap gap-2">
      {TABS.map((tab) => {
        const isActive =
          tab.href === "/dashboard/dyslexic"
            ? pathname === tab.href
            : pathname.startsWith(tab.href);

        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`rounded-base border-2 px-4 py-2 text-xs font-mono font-bold uppercase transition-all ${
              isActive
                ? "bg-orange text-black border-black shadow-light translate-x-[1px] translate-y-[1px]"
                : "border-border bg-[#141418] text-zinc-300 hover:bg-[#181820] hover:text-white"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function StageBadge({ stage }: { stage: CompanyStage }) {
  return (
    <span
      className={`inline-block rounded-base border-2 border-border px-2.5 py-0.5 text-[11px] font-mono font-bold whitespace-nowrap shadow-light ${stageVariant(stage)}`}
    >
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}

/**
 * Connection indicator.
 *
 * Only shown when the stream is not live — a working connection needs no
 * explanation, but silently-stale data does.
 */
export function StreamIndicator({ status }: { status: StreamStatus }) {
  if (status === "live") return null;

  return (
    <span className="flex items-center gap-2 text-xs font-mono text-zinc-400">
      <span
        className={`size-2 rounded-full ${
          status === "degraded" ? "bg-orange" : "bg-white/40 animate-pulse"
        }`}
      />
      {status === "degraded" ? "Live updates standby &bull; polling active" : "Connecting…"}
    </span>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl sm:text-3xl font-heading font-black tracking-tight text-white uppercase">{title}</h1>
        {description && (
          <p className="mt-1 text-xs sm:text-sm text-zinc-300 font-base">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-base border-2 border-red-500 bg-red-950/80 px-4 py-3 text-xs font-mono font-bold text-red-200 shadow-light">
      {message}
    </div>
  );
}

