"use client";

export default function DashboardFooter() {
  return (
    <footer className="mt-12 border-t-2 border-[#120f0a] bg-[#d0cfce] p-5 text-[#120f0a]">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[#413f3b] sm:flex-row sm:items-center sm:justify-between">
        <span>bits&amp;bytes™ motherboard</span>
        <span>Internal workspace · {new Date().getFullYear()}</span>
      </div>
    </footer>
  );
}
