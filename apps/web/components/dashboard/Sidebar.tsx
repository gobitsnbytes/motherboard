"use client";

import React, { useState, useCallback } from "react";
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
} from "lucide-react";

const navItems = [
  { label: "Overview", href: "/dashboard/overview", icon: LayoutDashboard },
  { label: "Members", href: "/dashboard/members", icon: Users },
  { label: "IAM", href: "/dashboard/iam", icon: Shield },
  { label: "Audit Log", href: "/dashboard/audit", icon: ScrollText },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
] as const;

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

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
            className={`flex items-center gap-3 rounded-base px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? "bg-main text-main-foreground border-2 border-border"
                : "text-foreground hover:bg-main/10 hover:text-main-foreground border-2 border-transparent"
            }`}
          >
            <item.icon className="size-4 shrink-0" />
            <span className="truncate">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 md:border-r-2 md:border-border md:bg-[#0d0d0d]">
        <div className="flex items-center gap-3 border-b-2 border-border px-4 py-3">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes logo"
            className="h-7 w-auto select-none"
          />
          <span className="font-heading font-bold text-sm tracking-wider text-foreground truncate">
            bits&bytes
          </span>
        </div>
        <div className="flex-1 overflow-auto p-3">
          <p className="mb-2 px-3 text-[10px] uppercase tracking-widest text-muted-foreground font-heading">
            Navigation
          </p>
          <NavList />
        </div>
        <div className="border-t-2 border-border p-3">
          <p className="text-[10px] text-muted-foreground font-heading uppercase tracking-widest text-center">
            motherboard v0.1
          </p>
        </div>
      </aside>

      {/* Mobile hamburger button */}
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        className="fixed top-3 left-3 z-30 md:hidden flex items-center justify-center size-9 rounded-base border-2 border-border bg-[#111] text-foreground"
        aria-label="Open sidebar"
      >
        <Menu className="size-5" />
      </button>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="fixed inset-0 bg-black/60"
            onClick={closeMobile}
            aria-hidden="true"
          />
          <aside className="fixed inset-y-0 left-0 w-72 bg-[#0d0d0d] border-r-2 border-border flex flex-col z-50">
            <div className="flex items-center justify-between border-b-2 border-border px-4 py-3">
              <div className="flex items-center gap-3">
                <img
                  src="https://gobitsnbytes.org/logo"
                  alt="bits&bytes logo"
                  className="h-7 w-auto select-none"
                />
                <span className="font-heading font-bold text-sm tracking-wider text-foreground">
                  bits&bytes
                </span>
              </div>
              <button
                type="button"
                onClick={closeMobile}
                className="flex items-center justify-center size-8 rounded-base text-foreground hover:bg-main hover:text-main-foreground transition-colors"
                aria-label="Close sidebar"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-3">
              <p className="mb-2 px-3 text-[10px] uppercase tracking-widest text-muted-foreground font-heading">
                Navigation
              </p>
              <NavList onNavigate={closeMobile} />
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
