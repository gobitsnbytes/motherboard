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
        <header className="sticky top-0 z-20 flex min-h-20 shrink-0 items-center justify-between border-b-2 border-black bg-[#f4f1ec] pl-16 pr-4 text-[#120f0a] sm:pr-6 md:px-8">
          <div className="flex items-center gap-3">
            <span className="border-2 border-orange bg-orange px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-black">
              Finance
            </span>
            <span className="hidden font-mono text-[11px] text-[#625b52] sm:inline">
              Virtual Ledger · Paper Accounts Only
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#625b52]">
            <span aria-hidden="true" className="size-2 bg-emerald-400" />
            <span className="hidden sm:inline">Internal ledger</span>
          </div>
        </header>
        <main className="motherboard-canvas flex-1 overflow-auto px-4 py-6 sm:px-8 sm:py-8 lg:px-10"><div className="mx-auto w-full max-w-[1480px]">{children}</div></main>
      </div>
    </div>
  );
}
