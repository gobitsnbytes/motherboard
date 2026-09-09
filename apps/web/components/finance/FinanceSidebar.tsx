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
    <aside
      style={{
        width: collapsed ? "64px" : "220px",
        transition: "width 220ms cubic-bezier(0.4,0,0.2,1)",
        background: "#3c0a12",
        borderRight: "2px solid #5b0f1a",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        position: "relative",
        zIndex: 10,
      }}
    >
      {/* Logo area */}
      <div style={{ padding: "20px 16px 16px", borderBottom: "2px solid #97192c" }}>
        <Link href="/finance/dashboard" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
          <img src="https://gobitsnbytes.org/logo" alt="bits&bytes™ logo" style={{ width: "28px", height: "auto", flexShrink: 0 }} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                style={{ fontFamily: "Inter, sans-serif", fontWeight: 800, fontSize: "13px", color: "#ffffff", letterSpacing: "0.12em", textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden" }}
              >
                Finance
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: "12px 10px", display: "flex", flexDirection: "column", gap: "4px" }}>
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "9px 10px",
                borderRadius: "4px",
                border: active ? "2px solid #fc920d" : "2px solid transparent",
                background: active ? "#97192c" : "transparent",
                color: active ? "#ffffff" : "rgba(255,255,255,0.7)",
                textDecoration: "none",
                fontFamily: "Inter, sans-serif",
                fontWeight: active ? 700 : 500,
                fontSize: "13px",
                letterSpacing: "0.02em",
                boxShadow: active ? "3px 3px 0 0 rgba(252,146,13,0.3)" : "none",
                transition: "all 150ms ease",
                whiteSpace: "nowrap",
                overflow: "hidden",
              }}
            >
              <span style={{ flexShrink: 0 }}>{item.icon}</span>
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: "auto" }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.12 }}
                    style={{ overflow: "hidden" }}
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        style={{
          margin: "12px 10px",
          padding: "8px",
          background: "transparent",
          border: "2px solid rgba(255,255,255,0.2)",
          borderRadius: "4px",
          color: "rgba(255,255,255,0.6)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "border-color 150ms, color 150ms",
        }}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          {collapsed
            ? <><polyline points="9 18 15 12 9 6" /></>
            : <><polyline points="15 18 9 12 15 6" /></>}
        </svg>
      </button>

      {/* Bottom label */}
      {!collapsed && (
        <div style={{ padding: "10px 16px 14px", borderTop: "2px solid #1e1e1e" }}>
          <div style={{ fontFamily: "Inter, sans-serif", fontSize: "9px", color: "rgba(255,255,255,0.55)", textTransform: "uppercase", letterSpacing: "0.15em" }}>
            GOBITSNBYTES FOUNDATION
          </div>
          <div style={{ fontFamily: "Inter, sans-serif", fontSize: "9px", color: "rgba(255,255,255,0.35)", marginTop: "2px" }}>
            Powered by RazorpayX
          </div>
        </div>
        {navigation()}
        <button type="button" onClick={() => setCollapsed((value) => !value)} className="m-3 min-h-11 border-2 border-black/50 px-3 text-sm text-white transition-colors hover:border-orange hover:text-orange" aria-label={collapsed ? "Expand finance navigation" : "Collapse finance navigation"}>{collapsed ? "→" : "Collapse"}</button>
      </aside>
      <button type="button" onClick={() => setMobileOpen(true)} className="fixed left-3 top-3 z-30 grid size-11 place-items-center border-2 border-black bg-burgundy text-white md:hidden" aria-label="Open finance navigation"><Menu size={19}/></button>
      {mobileOpen && <div className="fixed inset-0 z-40 md:hidden"><button type="button" aria-label="Close finance navigation" onClick={() => setMobileOpen(false)} className="absolute inset-0 w-full bg-black/70"/><aside className="relative z-10 flex h-full w-72 flex-col border-r-2 border-black bg-burgundy"><div className="flex items-center justify-between border-b-2 border-black/40 px-4 py-4"><span className="font-heading text-sm font-black text-white">Finance</span><button type="button" onClick={() => setMobileOpen(false)} className="grid size-11 place-items-center border-2 border-black/50 text-white" aria-label="Close finance navigation"><X size={18}/></button></div>{navigation(() => setMobileOpen(false), false)}</aside></div>}
    </>
  );
}
