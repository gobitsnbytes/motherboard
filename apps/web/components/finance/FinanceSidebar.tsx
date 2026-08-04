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
      style={{
        width: collapsed ? "64px" : "220px",
        transition: "width 220ms cubic-bezier(0.4,0,0.2,1)",
        background: "#111111",
        borderRight: "2px solid #1e1e1e",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        position: "relative",
        zIndex: 10,
      }}
    >
      {/* Logo area */}
      <div style={{ padding: "20px 16px 16px", borderBottom: "2px solid #1e1e1e" }}>
        <Link href="/finance/dashboard" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
          <img src="https://gobitsnbytes.org/logo" alt="bits&bytes™ logo" style={{ width: "28px", height: "auto", flexShrink: 0 }} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                style={{ fontFamily: "Inter, sans-serif", fontWeight: 800, fontSize: "13px", color: "#ffffff", letterSpacing: "0.05em", textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden" }}
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
                background: active ? "rgba(252,146,13,0.1)" : "transparent",
                color: active ? "#fc920d" : "#9a9a9a",
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
          border: "2px solid #2a2a2a",
          borderRadius: "4px",
          color: "#555",
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
          <div style={{ fontFamily: "Inter, sans-serif", fontSize: "9px", color: "#333", textTransform: "uppercase", letterSpacing: "0.15em" }}>
            GOBITSNBYTES FOUNDATION
          </div>
          <div style={{ fontFamily: "Inter, sans-serif", fontSize: "9px", color: "#2a2a2a", marginTop: "2px" }}>
            Powered by RazorpayX
          </div>
        </div>
      )}
    </aside>
  );
}
