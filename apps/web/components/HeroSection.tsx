"use client";

import React from "react";
import { motion } from "framer-motion";
import BlurText from "./BlurText";
import Link from "next/link";
import { useSession } from "next-auth/react";
import RefractiveGlassBackground from "./RefractiveGlassBackground";

export default function HeroSection() {
  const { data: session, status } = useSession();
  const isAuthenticated = status === "authenticated" && !!session;

  return (
    <section
      id="home"
      className="h-screen w-full relative flex flex-col justify-between items-center overflow-hidden bg-black select-none font-body py-8 md:py-12 px-6"
    >
      {/* Background Refractive Glass */}
      <RefractiveGlassBackground />

      {/* Top Navbar */}
      <nav className="fixed top-6 left-0 right-0 px-8 lg:px-16 z-50 flex items-center justify-between pointer-events-none">
        {/* Left: Logo & Naming */}
        <div className="flex items-center gap-3 pointer-events-auto">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes™ logo"
            className="h-8 w-auto select-none"
          />
          <span className="font-heading font-black text-lg tracking-wider text-white">
            motherboard
          </span>
        </div>

        {/* Right: Badge */}
        <div className="flex items-center gap-2 bg-burgundy/40 border border-burgundy/30 text-white px-4 py-1.5 text-xs font-bold uppercase tracking-wider rounded-full pointer-events-auto select-none backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          Cockpit v0.2.0 Active
        </div>
      </nav>

      {/* Centered Card */}
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center max-w-sm mx-auto w-full pt-16">
        <motion.div
          initial={{ opacity: 0, y: 20, filter: "blur(10px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="liquid-glass rounded-2xl p-8 flex flex-col items-center text-center w-full shadow-2xl border border-white/10"
          style={{
            backgroundColor: "rgba(18, 15, 10, 0.65)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
          }}
        >
          {/* Logo container */}
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5 border border-white/10"
            style={{ backgroundColor: "rgba(255, 255, 255, 0.05)" }}
          >
            <img
              src="https://gobitsnbytes.org/logo"
              alt="bits&bytes™ logo"
              className="w-7 h-auto"
            />
          </div>

          {/* Heading */}
          <h1 className="text-3xl md:text-4xl font-heading font-extrabold text-white leading-none tracking-tight mb-3">
            <BlurText text="bits&bytes Operations" />
          </h1>

          {/* Subtitle */}
          <p className="text-xs md:text-sm text-white/70 font-body leading-relaxed mb-6">
            The high-agency internal operational cockpit for GOBITSNBYTES FOUNDATION.
          </p>

          <Link
            href={isAuthenticated ? "/dashboard/overview" : "/login"}
            className="w-full mb-6 rounded-xl bg-gradient-to-r from-amber-500 to-orange text-black font-heading font-bold py-3 px-4 text-center transition-all duration-200 hover:scale-[1.02] shadow-lg shadow-amber-500/10"
          >
            {isAuthenticated ? "Enter Cockpit →" : "Access Platform"}
          </Link>
          {/* Info Section */}
          <div className="flex flex-col gap-2.5 w-full border-t border-white/10 pt-5 text-xs text-white/70">
            <div className="flex justify-between items-center px-1">
              <span className="font-heading uppercase tracking-wider text-orange font-bold">
                Scope
              </span>
              <span className="font-body text-white">
                Strictly Internal Tool
              </span>
            </div>
            <div className="flex justify-between items-center px-1">
              <span className="font-heading uppercase tracking-wider text-orange font-bold">
                Teammates
              </span>
              <span className="font-body text-white">~100 active members</span>
            </div>
            <div className="flex justify-between items-center px-1">
              <span className="font-heading uppercase tracking-wider text-orange font-bold">
                Access Control
              </span>
              <span className="font-body text-white">Invite-based access</span>
            </div>
          </div>

          {/* Links Section */}
          <div className="flex justify-center gap-4 w-full border-t border-white/10 pt-5 mt-5 text-xs">
            <a
              href="https://gobitsnbytes.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/60 hover:text-orange transition-colors duration-200 font-heading uppercase tracking-wider font-semibold"
            >
              gobitsnbytes.org
            </a>
            <span className="text-white/20">•</span>
            <a
              href="https://github.com/gobitsnbytes/motherboard"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/60 hover:text-orange transition-colors duration-200 font-heading uppercase tracking-wider font-semibold"
            >
              GitHub
            </a>
          </div>
        </motion.div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 text-[10px] text-white/40 font-heading tracking-widest uppercase text-center mt-auto pt-4 border-t border-burgundy/5 w-full max-w-sm">
        <div>built with ❤️ by the techies of bits&bytes™</div>
      </footer>
    </section>
  );
}
