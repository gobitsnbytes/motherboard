import React from "react";
import FinanceSidebar from "../../components/finance/FinanceSidebar";

export const metadata = {
  title: "Finance — bits&bytes™ Motherboard",
  description: "GOBITSNBYTES FOUNDATION internal virtual ledger and banking portal.",
};

export default function FinanceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        width: "100vw",
        overflow: "hidden",
        background: "#f8f1e7",
        color: "#120f0a",
      }}
    >
      {/* Sidebar */}
      <FinanceSidebar />

      {/* Main content area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Top bar */}
        <header
          style={{
            height: "56px",
            borderBottom: "2px solid #5b0f1a",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            flexShrink: 0,
            background: "#3c0a12",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: "11px",
                fontWeight: 700,
                color: "#fc920d",
                textTransform: "uppercase",
                letterSpacing: "0.15em",
                border: "1.5px solid rgba(252,146,13,0.35)",
                padding: "3px 8px",
                borderRadius: "3px",
                background: "rgba(252,146,13,0.08)",
              }}
            >
              Finance Portal
            </span>
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: "10px",
                color: "rgba(255,255,255,0.55)",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
              }}
            >
              Virtual Ledger · Paper Accounts Only
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#625b52]">
            <span aria-hidden="true" className="size-2 bg-emerald-400" />
            <span className="hidden sm:inline">Internal ledger</span>
          </div>
        </header>

        {/* Page content */}
          <main style={{ flex: 1, overflow: "auto", padding: "28px", background: "#f8f1e7" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
