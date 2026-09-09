"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { ArrowRight, FileCheck2, GitBranch, ShieldCheck, type LucideIcon } from "lucide-react";

const FEATURES: Array<{ icon: LucideIcon; title: string; copy: string }> = [
  { icon: ShieldCheck, title: "Identity & access", copy: "Clear roles and an auditable access path." },
  { icon: GitBranch, title: "Coordination", copy: "Projects, meetings, and decisions that stay connected." },
  { icon: FileCheck2, title: "Evidence", copy: "Forms, signatures, and records people can find later." },
];

export default function HeroSection() {
  const { data: session, status } = useSession();
  const isAuthenticated = status === "authenticated" && !!session;

  return (
    <section id="home" className="min-h-screen bg-[#f4f1ec] text-[#120f0a]">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-5 py-5 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between border-b border-[#120f0a]/20 pb-5">
          <Link href="/" className="flex items-center gap-3" aria-label="bits&bytes motherboard home">
            <div className="grid size-10 place-items-center bg-[#97192c] text-sm font-black text-white shadow-[4px_4px_0_#120f0a]">b&b</div>
            <div>
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-[#97192c]">bits&bytes™</p>
              <p className="font-serif text-lg leading-none">motherboard</p>
            </div>
          </Link>
          <span className="hidden font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[#120f0a]/60 sm:block">Internal coordination</span>
        </header>

        <main className="grid flex-1 items-center gap-12 py-16 lg:grid-cols-[1.15fr_0.85fr] lg:gap-20">
          <div>
            <p className="mb-6 font-mono text-xs font-bold uppercase tracking-[0.2em] text-[#97192c]">One shared operating picture</p>
            <h1 className="max-w-3xl font-serif text-5xl leading-[0.95] tracking-[-0.04em] sm:text-7xl lg:text-8xl">Make the work visible. Keep the people moving.</h1>
            <p className="mt-8 max-w-xl text-lg leading-8 text-[#120f0a]/70">Motherboard is the internal workspace for bits&bytes™ teams: people, projects, meetings, signatures, and evidence in one place.</p>
            <div className="mt-10 flex flex-col gap-3 sm:flex-row">
              <Link href={isAuthenticated ? "/dashboard/overview" : "/login"} className="inline-flex items-center justify-center gap-3 border-2 border-[#120f0a] bg-[#97192c] px-6 py-4 font-mono text-xs font-bold uppercase tracking-[0.14em] text-white shadow-[5px_5px_0_#120f0a] transition-transform hover:translate-x-1 hover:translate-y-1 hover:shadow-none">
                {isAuthenticated ? "Open workspace" : "Sign in with Discord"}<ArrowRight className="size-4" />
              </Link>
              <Link href="/form/example" className="inline-flex items-center justify-center border-2 border-[#120f0a]/25 px-6 py-4 font-mono text-xs font-bold uppercase tracking-[0.14em] transition-colors hover:border-[#97192c] hover:text-[#97192c]">View a public form</Link>
            </div>
          </div>

          <aside className="border-2 border-[#120f0a] bg-white p-6 shadow-[8px_8px_0_#97192c] sm:p-8">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[#97192c]">What lives here</p>
            <div className="mt-6 divide-y divide-[#120f0a]/15">
              {FEATURES.map(({ icon: Icon, title, copy }) => (
                <div key={title} className="flex gap-4 py-5 first:pt-0 last:pb-0">
                  <div className="grid size-10 shrink-0 place-items-center bg-[#fc920d] text-[#120f0a]"><Icon className="size-5" /></div>
                  <div><h2 className="font-serif text-xl">{title}</h2><p className="mt-1 text-sm leading-6 text-[#120f0a]/60">{copy}</p></div>
                </div>
              ))}
            </div>
          </aside>
        </main>

        <footer className="flex flex-col gap-2 border-t border-[#120f0a]/20 pt-5 font-mono text-[10px] uppercase tracking-[0.14em] text-[#120f0a]/55 sm:flex-row sm:items-center sm:justify-between">
          <span>bits&bytes™ by GOBITSNBYTES FOUNDATION</span>
          <span>Invite-only internal workspace</span>
        </footer>
      </div>
    </section>
  );
}
