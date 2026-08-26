"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

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

  return (
    <aside
      className={`relative z-10 flex shrink-0 flex-col border-r-2 border-border bg-main transition-[width] duration-200 ${collapsed ? "w-16" : "w-[220px]"}`}
    >
      {/* Logo area */}
      <div className="border-b-2 border-border px-4 pb-4 pt-5">
        <Link href="/finance/dashboard" className="flex items-center gap-2.5 no-underline">
          <img src="https://gobitsnbytes.org/logo" alt="bits&bytes™ logo" className="h-auto w-7 shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden whitespace-nowrap font-heading text-[13px] font-extrabold uppercase tracking-[0.05em] text-white"
              >
                Finance
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col gap-1 p-2.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 whitespace-nowrap overflow-hidden rounded-base border-2 px-2.5 py-2 font-heading text-[13px] no-underline transition-all duration-150 ${
                active
                  ? "border-orange bg-orange/10 font-bold text-orange shadow-shadow"
                  : "border-transparent font-medium text-muted-foreground hover:border-border hover:text-foreground"
              }`}
            >
              <span className="shrink-0">{item.icon}</span>
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: "auto" }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.12 }}
                    className="overflow-hidden"
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
        className="mx-2.5 mb-3 flex items-center justify-center rounded-base border-2 border-border bg-transparent p-2 text-muted-foreground transition-colors duration-150 hover:border-orange hover:text-orange"
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
        <div className="border-t-2 border-border px-4 pb-3.5 pt-2.5">
          <div className="font-heading text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
            GOBITSNBYTES FOUNDATION
          </div>
          <div className="mt-0.5 font-heading text-[9px] text-muted-foreground/60">
            Powered by RazorpayX
          </div>
        </div>
      )}
    </aside>
  );
}
