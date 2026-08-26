import React from "react";
import FinanceSidebar from "../../components/finance/FinanceSidebar";

export const metadata = {
  title: "Finance — bits&bytes™ Motherboard",
  description: "GOBITSNBYTES FOUNDATION internal virtual ledger and banking portal.",
};

export default function FinanceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground font-base">
      {/* Sidebar */}
      <FinanceSidebar />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b-2 border-border bg-main px-6">
          <div className="flex items-center gap-3">
            <span className="rounded-base border-2 border-orange/35 bg-orange/10 px-2 py-0.5 font-heading text-[11px] font-bold uppercase tracking-[0.15em] text-orange">
              Finance Portal
            </span>
            <span className="font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              Virtual Ledger · Paper Accounts Only
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-block size-2 rounded-full bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]" />
            <span className="font-heading text-[11px] tracking-[0.05em] text-muted-foreground">
              GOBITSNBYTES FOUNDATION
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-7">{children}</main>
      </div>
    </div>
  );
}
