"use client";

import React, { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Shield,
  ScrollText,
  Settings,
  Menu,
  X,
  Puzzle,
  Calendar,
  Handshake,
  FileSignature,
  Coins,
  FileCheck,
  ClipboardList,
  GitBranch,
  UserCheck,
} from "lucide-react";
import * as Lucide from "lucide-react";
import { APP_VERSION_LABEL } from "../../lib/version";

interface UiPanel {
  id: string;
  title: string;
  route_segment: string;
  placement: string;
  required_permission?: string;
  icon: string;
}

interface ActivePlugin {
  id: string;
  name: string;
  version: string;
  ui_panels: UiPanel[];
}

const navGroups = [
  { label: "Overview", items: [
    { label: "Dashboard", href: "/dashboard/overview", icon: LayoutDashboard },
    { label: "Profile", href: "/dashboard/profile", icon: UserCheck },
  ] },
  { label: "Work", items: [
    { label: "Meetings", href: "/dashboard/meetings", icon: Calendar },
    { label: "Forms", href: "/dashboard/forms", icon: ClipboardList },
    { label: "Signatures", href: "/dashboard/signatures", icon: FileSignature },
    { label: "Contracts", href: "/dashboard/contract-assistant", icon: FileCheck },
    { label: "Dyslexic CRM", href: "/dashboard/dyslexic", icon: Handshake },
  ] },
  { label: "Governance", items: [
    { label: "Members", href: "/dashboard/members", icon: Users },
    { label: "IAM", href: "/dashboard/iam", icon: Shield },
    { label: "Audit log", href: "/dashboard/audit", icon: ScrollText },
  ] },
  { label: "Network", items: [
    { label: "Forks", href: "/dashboard/forks", icon: GitBranch },
    { label: "Finance", href: "/dashboard/finance", icon: Coins },
    { label: "Settings", href: "/dashboard/settings", icon: Settings },
  ] },
] as const;

function DynamicIcon({ name, className }: { name: string; className?: string }) {
  const icons = Lucide as unknown as Record<string, React.ComponentType<{ className?: string }> | undefined>;
  const IconComponent = icons[name] ?? Puzzle;
  return <IconComponent className={className} />;
}

function NavList({
  plugins,
  onNavigate,
}: {
  plugins: ActivePlugin[];
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  // Extract all sidebar panels from active plugins
  const sidebarPanels = plugins.flatMap((plugin) =>
    plugin.ui_panels
      .filter((panel) => panel.placement === "sidebar")
      .map((panel) => ({
        ...panel,
        pluginId: plugin.id,
        href: `/dashboard/plugins/${plugin.id}/${panel.route_segment}`,
      }))
  );

  return (
    <nav aria-label="Primary navigation" className="flex flex-col gap-1">
      {navGroups.map((group) => (
        <div key={group.label} className="space-y-1">
          <p className="px-3 text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-zinc-500">{group.label}</p>
          {group.items.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link key={item.href} href={item.href} onClick={onNavigate} className={`flex min-h-11 items-center gap-3 rounded-base border-2 px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "border-orange bg-orange text-black shadow-light" : "border-transparent text-zinc-300 hover:border-zinc-600 hover:bg-white/5 hover:text-white"}`}>
                <item.icon className="size-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      ))}

      {sidebarPanels.length > 0 && (
        <>
          <p className="mt-4 mb-2 px-3 text-[10px] uppercase tracking-widest text-muted-foreground font-heading">
            Plugins
          </p>
          {sidebarPanels.map((panel) => {
            const isActive =
              pathname === panel.href || pathname.startsWith(panel.href + "/");
            return (
              <Link
                key={panel.id}
                href={panel.href}
                onClick={onNavigate}
                className={`flex min-h-11 items-center gap-3 rounded-base px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                  ? "border-2 border-orange bg-orange text-black shadow-light"
                  : "border-2 border-transparent text-zinc-300 hover:border-zinc-600 hover:bg-white/5 hover:text-white"
                }`}
              >
                <DynamicIcon name={panel.icon} className="size-4 shrink-0" />
                <span className="truncate">{panel.title}</span>
              </Link>
            );
          })}
        </>
      )}
    </nav>
  );
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [plugins, setPlugins] = useState<ActivePlugin[]>([]);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  useEffect(() => {
    async function fetchPlugins() {
      try {
        const res = await fetch("/api/plugins/active");
        if (res.ok) {
          const data = await res.json();
          setPlugins(data);
        }
      } catch (err) {
        console.error("Failed to fetch active plugins in sidebar:", err);
      }
    }
    fetchPlugins();
  }, []);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:fixed md:inset-y-0 md:flex md:w-72 md:flex-col md:border-r-2 md:border-black md:bg-burgundy">
        <div className="flex items-center gap-3 border-b-2 border-black/40 px-5 py-5">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes logo"
            className="h-7 w-auto select-none"
          />
          <div className="flex flex-col">
            <span className="font-heading text-sm font-black tracking-wide text-white truncate">
              bits&bytes™
            </span>
            <span className="font-mono text-[9px] text-white/65 uppercase tracking-widest">
              MOTHERBOARD
            </span>
          </div>
        </div>
        <div className="flex-1 overflow-auto px-3 py-5">
          <NavList plugins={plugins} />
        </div>
        <div className="border-t-2 border-black/40 p-4">
          <p className="text-[10px] text-white/60 font-mono uppercase tracking-widest text-center">
            motherboard {APP_VERSION_LABEL}
          </p>
        </div>
      </aside>

      {/* Mobile hamburger button */}
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        className="fixed top-3 left-3 z-30 md:hidden flex items-center justify-center size-11 rounded-base border-2 border-black bg-burgundy text-white shadow-light"
        aria-label="Open sidebar"
      >
        <Menu className="size-5" />
      </button>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="fixed inset-0 bg-black/80"
            onClick={closeMobile}
            aria-hidden="true"
          />
          <aside className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r-2 border-black bg-burgundy">
            <div className="flex items-center justify-between border-b-2 border-black/40 px-4 py-4">
              <div className="flex items-center gap-3">
                <img
                  src="https://gobitsnbytes.org/logo"
                  alt="bits&bytes logo"
                  className="h-7 w-auto select-none"
                />
                <span className="font-heading font-black text-sm tracking-wider text-white uppercase">
                  bits&bytes™
                </span>
              </div>
              <button
                type="button"
                onClick={closeMobile}
                className="flex size-11 items-center justify-center rounded-base border-2 border-black/50 text-white transition-colors hover:border-orange hover:text-orange"
                aria-label="Close sidebar"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-3">
              <NavList plugins={plugins} onNavigate={closeMobile} />
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
