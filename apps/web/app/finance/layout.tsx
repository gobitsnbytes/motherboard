import React from "react";
import FinanceSidebar from "../../components/finance/FinanceSidebar";

export const metadata = {
  title: "Finance — bits&bytes™ Motherboard",
  description: "GOBITSNBYTES FOUNDATION internal virtual ledger and banking portal.",
};

export default function FinanceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="motherboard-shell flex min-h-screen text-foreground font-base">
      <FinanceSidebar />
      <div className="flex min-w-0 flex-1 flex-col md:ml-64">
        <header className="sticky top-0 z-20 flex min-h-16 shrink-0 items-center justify-between border-b-2 border-zinc-700 bg-[#111115] pl-16 pr-4 sm:pr-6 md:px-6">
          <div className="flex items-center gap-3">
            <span className="border-2 border-orange bg-orange px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-black">
              Finance
            </span>
            <span className="hidden font-mono text-[11px] text-zinc-400 sm:inline">
              Virtual Ledger · Paper Accounts Only
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-300">
            <span aria-hidden="true" className="size-2 bg-emerald-400" />
            <span className="hidden sm:inline">Internal ledger</span>
          </div>
        </header>
        <main className="motherboard-canvas flex-1 overflow-auto p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
