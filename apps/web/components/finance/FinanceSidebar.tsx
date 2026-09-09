"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

const NAV_ITEMS = [
  {
    href: "/dashboard/overview",
    label: "Exit to Dashboard",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
      </svg>
    ),
  },
  {
    href: "/finance/dashboard",
    label: "Dashboard",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
  },
  {
    href: "/finance/accounts",
    label: "Accounts",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="2" /><line x1="2" y1="10" x2="22" y2="10" />
      </svg>
    ),
  },
  {
    href: "/finance/cards",
    label: "Cards",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="4" width="22" height="16" rx="2" /><line x1="1" y1="10" x2="23" y2="10" />
      </svg>
    ),
  },
  {
    href: "/finance/requests",
    label: "Requests",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
  },
];

export default function FinanceSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const navigation = (close?: () => void, compact = collapsed) => <nav aria-label="Finance navigation" className="flex flex-1 flex-col gap-1 p-3">
    {NAV_ITEMS.map((item) => {
      const active = pathname === item.href || pathname.startsWith(item.href + "/");
      return <Link key={item.href} href={item.href} onClick={close} className={`flex min-h-11 items-center gap-3 overflow-hidden whitespace-nowrap rounded-base border-2 px-3 text-sm font-medium no-underline transition-colors ${active ? "border-[#120f0a] bg-orange text-black shadow-light" : "border-transparent text-white/75 hover:border-black/40 hover:bg-black/10 hover:text-white"}`}>
        <span className="shrink-0">{item.icon}</span>
        {!compact && <span className="overflow-hidden">{item.label}</span>}
      </Link>;
    })}
  </nav>;

  return (
    <>
      <aside className={`hidden shrink-0 flex-col bg-burgundy text-white transition-[width] duration-200 md:flex ${collapsed ? "w-16" : "w-56"}`}>
        <div className="border-b-2 border-black/30 px-4 py-5">
          <Link href="/finance/dashboard" className="flex items-center gap-3 font-heading text-sm font-black uppercase tracking-[0.12em]">
            <span className="grid size-8 shrink-0 place-items-center border-2 border-black bg-orange text-black">$</span>
            {!collapsed && <span>Finance</span>}
          </Link>
        </div>
        {navigation()}
        <button type="button" onClick={() => setCollapsed((value) => !value)} className="m-3 min-h-11 border-2 border-black/50 px-3 text-sm text-white transition-colors hover:border-orange hover:text-orange" aria-label={collapsed ? "Expand finance navigation" : "Collapse finance navigation"}>{collapsed ? "→" : "Collapse"}</button>
      </aside>
      <button type="button" onClick={() => setMobileOpen(true)} className="fixed left-3 top-3 z-30 grid size-11 place-items-center border-2 border-black bg-burgundy text-white md:hidden" aria-label="Open finance navigation"><Menu size={19}/></button>
      {mobileOpen && <div className="fixed inset-0 z-40 md:hidden"><button type="button" aria-label="Close finance navigation" onClick={() => setMobileOpen(false)} className="absolute inset-0 w-full bg-black/70"/><aside className="relative z-10 flex h-full w-72 flex-col border-r-2 border-black bg-burgundy"><div className="flex items-center justify-between border-b-2 border-black/40 px-4 py-4"><span className="font-heading text-sm font-black text-white">Finance</span><button type="button" onClick={() => setMobileOpen(false)} className="grid size-11 place-items-center border-2 border-black/50 text-white" aria-label="Close finance navigation"><X size={18}/></button></div>{navigation(() => setMobileOpen(false), false)}</aside></div>}
    </>
  );
}
