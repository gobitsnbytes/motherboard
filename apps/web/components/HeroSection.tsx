"use client";

import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { ShieldCheck, Terminal, Compass, ArrowRight, Lock } from "lucide-react";

export default function HeroSection() {
  const { data: session, status } = useSession();
  const isAuthenticated = status === "authenticated" && !!session;

  return (
    <section
      id="home"
      className="min-h-screen w-full relative flex flex-col justify-between items-center bg-[#0a0a0c] select-none font-body py-6 md:py-10 px-4 blueprint-dot-grid"
    >
      {/* Top Navbar */}
      <header className="w-full max-w-6xl flex items-center justify-between z-20 pb-4 border-b-2 border-border">
        {/* Left: Brand Identity */}
        <div className="flex items-center gap-3">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes™ logo"
            className="h-8 w-auto select-none"
          />
          <div className="flex flex-col">
            <span className="font-heading font-black text-base md:text-lg tracking-wider text-white uppercase">
              bits&bytes™ motherboard
            </span>
            <span className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest hidden sm:inline">
              OPERATIONS COCKPIT // 26.8467° N, 80.9462° E
            </span>
          </div>
        </div>

        {/* Right: Telemetry Badge */}
        <div className="flex items-center gap-2 border-2 border-border bg-[#121216] text-white px-3 py-1.5 text-xs font-mono font-bold tracking-wider rounded-base shadow-light select-none">
          <span className="size-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>SYSTEM ONLINE</span>
        </div>
      </header>

      {/* Main Blueprint Center Box */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center max-w-md mx-auto w-full my-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="relative w-full rounded-base border-2 border-border bg-[#121216] p-6 sm:p-8 text-center shadow-heavy"
        >
          {/* Top Tag */}
          <div className="absolute -top-3 left-4 bg-orange text-black font-mono font-black text-[10px] uppercase px-2.5 py-0.5 border-2 border-black shadow-[2px_2px_0px_#000]">
            INTERNAL DISPATCH // DESK 01
          </div>

          {/* Logo Mark Container */}
          <div className="mx-auto size-14 rounded-base border-2 border-border bg-black flex items-center justify-center mb-5 shadow-light">
            <img
              src="https://gobitsnbytes.org/logo"
              alt="bits&bytes™ cube mark"
              className="w-7 h-auto"
            />
          </div>

          {/* Heading */}
          <h1 className="text-2xl sm:text-3xl font-heading font-black text-white uppercase tracking-tight mb-2">
            Operations Cockpit
          </h1>

          {/* Subtitle */}
          <p className="text-xs sm:text-sm text-zinc-300 font-base leading-relaxed mb-6">
            The high-agency internal operations layer &amp; coordination engine for <strong className="text-white">GOBITSNBYTES FOUNDATION</strong>.
          </p>

          {/* Primary Action Button */}
          <Link
            href={isAuthenticated ? "/dashboard/overview" : "/login"}
            className="w-full mb-6 inline-flex items-center justify-center gap-2 rounded-base bg-orange text-black font-heading font-black text-sm uppercase tracking-wider py-3.5 px-4 border-2 border-border shadow-dark hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
          >
            <span>{isAuthenticated ? "Enter Cockpit" : "Sign In with Discord"}</span>
            <ArrowRight className="size-4" />
          </Link>

          {/* Technical Specs Table */}
          <div className="flex flex-col gap-2 w-full border-t-2 border-border pt-4 text-xs font-mono">
            <div className="flex justify-between items-center px-1">
              <span className="text-zinc-400 uppercase font-semibold">Scope</span>
              <span className="text-white font-bold">Strictly Internal Tool</span>
            </div>
            <div className="flex justify-between items-center px-1">
              <span className="text-zinc-400 uppercase font-semibold">Legal Entity</span>
              <span className="text-white font-bold">Section 8 Non-Profit</span>
            </div>
            <div className="flex justify-between items-center px-1">
              <span className="text-zinc-400 uppercase font-semibold">Access Policy</span>
              <span className="text-amber-400 font-bold">Invite-Only (OAuth)</span>
            </div>
            <div className="flex justify-between items-center px-1">
              <span className="text-zinc-400 uppercase font-semibold">Compliance</span>
              <span className="text-emerald-400 font-bold">POCSO &amp; DPDP 2023</span>
            </div>
          </div>

          {/* External Links */}
          <div className="flex justify-center items-center gap-4 w-full border-t-2 border-border pt-4 mt-4 text-xs font-mono font-bold">
            <a
              href="https://gobitsnbytes.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-zinc-400 hover:text-orange transition-colors uppercase tracking-wider"
            >
              gobitsnbytes.org
            </a>
            <span className="text-zinc-600">•</span>
            <a
              href="https://github.com/gobitsnbytes/motherboard"
              target="_blank"
              rel="noopener noreferrer"
              className="text-zinc-400 hover:text-orange transition-colors uppercase tracking-wider"
            >
              GitHub
            </a>
          </div>
        </motion.div>
      </main>

      {/* Footer Notice */}
      <footer className="w-full max-w-6xl z-20 pt-4 border-t-2 border-border flex flex-col sm:flex-row items-center justify-between text-[11px] font-mono text-zinc-400 uppercase tracking-widest gap-2">
        <div>&copy; {new Date().getFullYear()} GOBITSNBYTES FOUNDATION (CIN License #186266)</div>
        <div>Getting ambitious teenagers to ship meaningful tech.</div>
      </footer>
    </section>
  );
}

