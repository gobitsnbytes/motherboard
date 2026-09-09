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

const navItems = [
  { label: "Overview", href: "/dashboard/overview", icon: LayoutDashboard },
  { label: "Setup Profile", href: "/dashboard/profile", icon: UserCheck },
  { label: "Contract Assistant", href: "/dashboard/contract-assistant", icon: FileCheck },
  { label: "Signatures", href: "/dashboard/signatures", icon: FileSignature },
  { label: "Forms", href: "/dashboard/forms", icon: ClipboardList },
  { label: "Meetings", href: "/dashboard/meetings", icon: Calendar },
  { label: "Dyslexic", href: "/dashboard/dyslexic", icon: Handshake },
  { label: "Members", href: "/dashboard/members", icon: Users },
  { label: "Forks", href: "/dashboard/forks", icon: GitBranch },
  { label: "Finance", href: "/dashboard/finance", icon: Coins },
  { label: "IAM", href: "/dashboard/iam", icon: Shield },
  { label: "Audit Log", href: "/dashboard/audit", icon: ScrollText },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
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
    <nav className="flex flex-col gap-1">
      {navItems.map((item) => {
        const isActive =
          pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`flex items-center gap-3 rounded-base px-3 py-2.5 text-sm font-medium transition-all ${
              isActive
                ? "bg-main text-main-foreground border-2 border-border shadow-light translate-x-[2px] translate-y-[2px]"
                : "text-foreground hover:bg-main/10 hover:text-foreground border-2 border-transparent"
            }`}
          >
            <item.icon className="size-4 shrink-0" />
            <span className="truncate">{item.label}</span>
          </Link>
        );
      })}

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
                className={`flex items-center gap-3 rounded-base px-3 py-2.5 text-sm font-medium transition-all ${
                  isActive
                    ? "bg-main text-main-foreground border-2 border-border shadow-light translate-x-[2px] translate-y-[2px]"
                    : "text-foreground hover:bg-main/10 hover:text-foreground border-2 border-transparent"
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
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 md:border-r-2 md:border-border md:bg-[#0d0d10]">
        <div className="flex items-center gap-3 border-b-2 border-border px-4 py-3.5 bg-[#121216]">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes logo"
            className="h-7 w-auto select-none"
          />
          <div className="flex flex-col">
            <span className="font-heading font-black text-sm tracking-wider text-white uppercase truncate">
              bits&bytes™
            </span>
            <span className="font-mono text-[9px] text-zinc-400 uppercase tracking-widest">
              MOTHERBOARD
            </span>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-3">
          <p className="mb-2 px-3 text-[10px] uppercase tracking-widest text-zinc-400 font-mono font-bold">
            Navigation
          </p>
          <NavList plugins={plugins} />
        </div>
        <div className="border-t-2 border-border p-3 bg-[#121216]">
          <p className="text-[10px] text-zinc-400 font-mono uppercase tracking-widest text-center">
            motherboard v0.2.0
          </p>
        </div>
      </aside>

      {/* Mobile hamburger button */}
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        className="fixed top-3 left-3 z-30 md:hidden flex items-center justify-center size-9 rounded-base border-2 border-border bg-[#121216] text-white shadow-light"
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
          <aside className="fixed inset-y-0 left-0 w-72 bg-[#0d0d10] border-r-2 border-border flex flex-col z-50">
            <div className="flex items-center justify-between border-b-2 border-border px-4 py-3.5 bg-[#121216]">
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
                className="flex items-center justify-center size-8 rounded-base text-zinc-300 hover:bg-main hover:text-white border border-border transition-colors"
                aria-label="Close sidebar"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-3">
              <p className="mb-2 px-3 text-[10px] uppercase tracking-widest text-zinc-400 font-mono font-bold">
                Navigation
              </p>
              <NavList plugins={plugins} onNavigate={closeMobile} />
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
