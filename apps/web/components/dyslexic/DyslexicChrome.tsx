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
            className={`rounded-base border-2 px-3 py-1.5 text-sm font-medium transition-all ${
              isActive
                ? "bg-main text-main-foreground border-border shadow-light translate-x-[2px] translate-y-[2px]"
                : "border-transparent text-foreground hover:bg-main/10"
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
      className={`inline-block rounded-base border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${stageVariant(stage)}`}
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
    <span className="flex items-center gap-2 text-xs text-muted-foreground">
      <span
        className={`size-2 rounded-full ${
          status === "degraded" ? "bg-orange" : "bg-white/40 animate-pulse"
        }`}
      />
      {status === "degraded" ? "Live updates unavailable — refreshing periodically" : "Connecting…"}
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
        <h1 className="text-2xl font-heading font-bold text-foreground">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground font-base">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-base border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      {message}
    </div>
  );
}
