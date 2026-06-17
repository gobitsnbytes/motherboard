"use client";

import React from 'react';
import { motion } from 'framer-motion';
import FadingVideo from './FadingVideo';
import BlurText from './BlurText';

const ArrowUpRight = ({ className = "w-5 h-5" }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
    <path d="M7 17L17 7M7 7h10v10" />
  </svg>
);

const BookOpenIcon = ({ className = "w-4 h-4" }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
    <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
  </svg>
);

export default function HeroSection() {
  return (
    <section id="home" className="min-h-screen w-full relative flex flex-col justify-between items-center overflow-x-hidden bg-black select-none font-body py-8">
      {/* Background Video */}
      <FadingVideo
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260418_080021_d598092b-c4c2-4e53-8e46-94cf9064cd50.mp4"
        className="absolute left-1/2 top-0 -translate-x-1/2 object-cover object-top z-0 opacity-40"
        style={{ width: "120%", height: "120%" }}
      />

      {/* Navbar (fixed top-4, px-8 / lg:px-16, z-50) */}
      <nav className="fixed top-4 left-0 right-0 px-8 lg:px-16 z-50 flex items-center justify-between pointer-events-none">
        {/* Left */}
        <div className="w-12 h-12 rounded-full flex items-center justify-center liquid-glass font-heading italic text-white text-2xl font-bold pointer-events-auto cursor-pointer hover:scale-105 transition-transform duration-300">
          a
        </div>

        {/* Center */}
        <div className="hidden md:flex items-center gap-1 liquid-glass rounded-full p-1.5 pointer-events-auto border border-burgundy/25">
          {['Governance', 'Chapter Sync', 'Scheduler Specs'].map((link, idx) => (
            <a
              key={idx}
              href={`#${link.toLowerCase().replace(' ', '-')}`}
              className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/90 hover:text-orange transition-colors font-heading"
            >
              {link}
            </a>
          ))}
          <div className="flex items-center gap-2 bg-burgundy text-white px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-full ml-2 select-none">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Platform Status
          </div>
        </div>

        {/* Right */}
        <div className="w-12 h-12 invisible"></div>
      </nav>

      {/* Bento Grid Content Wrapper (z-10 layer) */}
      <div className="relative z-10 w-full flex-1 flex flex-col lg:flex-row gap-8 items-center lg:items-stretch justify-center pt-28 px-6 lg:px-12 max-w-7xl mx-auto">
        
        {/* Left Column: Heading & CTAs (approx 40% width) */}
        <div className="flex flex-col justify-center items-center lg:items-start text-center lg:text-left lg:w-5/12 shrink-0">
          {/* Badge */}
          <motion.div
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            className="inline-flex items-center gap-2 p-1 liquid-glass rounded-full border border-burgundy/20"
          >
            <span className="bg-burgundy text-white px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full select-none">
              Internal
            </span>
            <span className="text-xs text-white/90 pr-3 font-heading tracking-wide uppercase font-medium">
              GOBITSNBYTES FOUNDATION
            </span>
          </motion.div>

          {/* Headline */}
          <h1 className="text-5xl md:text-6xl lg:text-[4.5rem] font-heading font-extrabold text-white leading-[0.95] tracking-tight mt-6 max-w-xl">
            <BlurText text="bits&bytes Operations Core" />
          </h1>

          {/* Subheading */}
          <motion.p
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6, ease: "easeOut" }}
            className="mt-6 text-sm text-white/70 max-w-md font-body leading-relaxed"
          >
            The internal operations platform and identity core for the bits&bytes™ network. 
            Automating chapter synchronization, governance rules, and meeting transcriptions.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.8, ease: "easeOut" }}
            className="flex items-center gap-4 mt-8"
          >
            <button className="liquid-glass rounded-full px-5 py-2.5 text-xs font-bold uppercase tracking-widest text-white flex items-center gap-1.5 border border-burgundy/45 hover:scale-105 hover:bg-burgundy/20 active:scale-95 transition-all duration-300">
              Operations API
              <ArrowUpRight className="w-4 h-4" />
            </button>
            
            <a
              href="https://github.com/gobitsnbytes/motherboard"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-white/90 hover:text-white transition-colors duration-200"
            >
              View Repository
              <span className="w-8 h-8 rounded-full flex items-center justify-center liquid-glass bg-white/5 border border-white/10">
                <BookOpenIcon className="w-3.5 h-3.5" />
              </span>
            </a>
          </motion.div>

          {/* Stats Row */}
          <motion.div
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.0, ease: "easeOut" }}
            className="flex flex-row items-stretch gap-4 mt-10 w-full justify-center lg:justify-start"
          >
            {/* Stat 1 */}
            <div className="liquid-glass p-4 w-[160px] rounded-[1rem] flex flex-col items-start border border-burgundy/10 hover:border-burgundy/30 transition-all duration-300">
              <svg className="w-5 h-5 text-orange" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="9" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
              </svg>
              <div className="mt-4">
                <div className="text-2xl font-heading font-black text-white leading-none">
                  90 Days
                </div>
                <div className="text-[10px] text-white/50 font-heading tracking-wider uppercase font-semibold mt-1.5">
                  Archival Limit
                </div>
              </div>
            </div>

            {/* Stat 2 */}
            <div className="liquid-glass p-4 w-[160px] rounded-[1rem] flex flex-col items-start border border-burgundy/10 hover:border-burgundy/30 transition-all duration-300">
              <svg className="w-5 h-5 text-orange" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <div className="mt-4">
                <div className="text-2xl font-heading font-black text-white leading-none">
                  Active
                </div>
                <div className="text-[10px] text-white/50 font-heading tracking-wider uppercase font-semibold mt-1.5">
                  Safeguarding Core
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Right Column: Bento Specifications Cards (approx 60% width) */}
        <div className="flex flex-col gap-6 lg:w-7/12 w-full justify-center">
          
          {/* Card 1: Legal & Executive */}
          <motion.div
            initial={{ opacity: 0, x: 40, filter: "blur(10px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.8, delay: 0.3, ease: "easeOut" }}
            whileHover={{ scale: 1.01, backgroundColor: "rgba(151, 25, 44, 0.05)" }}
            className="liquid-glass rounded-[1.25rem] p-6 border border-burgundy/10 cursor-pointer transition-all duration-300"
            id="governance"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-[0.5rem] flex items-center justify-center bg-burgundy/20 text-orange shrink-0">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <h3 className="font-heading font-bold uppercase tracking-wider text-sm text-white/95">
                Corporate & Governance Registry
              </h3>
            </div>
            
            <p className="text-xs text-white/70 font-body leading-relaxed mb-4">
              <strong>GOBITSNBYTES FOUNDATION</strong> is a Section 8 licensed non-profit company (UP, India) limited by guarantee. Liability is restricted strictly to educational/charitable object promotion.
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-burgundy/10 pt-4 text-[11px] text-white/80">
              <div>
                <span className="block text-orange font-heading uppercase tracking-wider text-[9px] font-bold">Board of Directors</span>
                <span className="block font-body mt-0.5">Vijay Prakash Singh Kushwaha</span>
                <span className="block font-body text-white/60">Sanjay Singh</span>
              </div>
              <div>
                <span className="block text-orange font-heading uppercase tracking-wider text-[9px] font-bold">Executive Officers</span>
                <span className="block font-body mt-0.5">Yash Vardhan Singh (CEO) · Akshat Kushwaha (CTO)</span>
                <span className="block font-body text-white/60">Aadrika Maurya (COO/CCO) · Devaansh Pathak (CFO)</span>
              </div>
            </div>
          </motion.div>

          {/* Card 2: Chapter Sync & Onboarding */}
          <motion.div
            initial={{ opacity: 0, x: 40, filter: "blur(10px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.8, delay: 0.5, ease: "easeOut" }}
            whileHover={{ scale: 1.01, backgroundColor: "rgba(151, 25, 44, 0.05)" }}
            className="liquid-glass rounded-[1.25rem] p-6 border border-burgundy/10 cursor-pointer transition-all duration-300"
            id="chapter-sync"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-[0.5rem] flex items-center justify-center bg-burgundy/20 text-orange shrink-0">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H18" />
                </svg>
              </div>
              <h3 className="font-heading font-bold uppercase tracking-wider text-sm text-white/95">
                Chapter Provisioning & Pulse Sync
              </h3>
            </div>
            
            <p className="text-xs text-white/70 font-body leading-relaxed mb-4">
              Sync workers verify Chapter status using automated 7-step onboarding checkpoints. Active state is maintained through weekly activity pulses using Discord commands.
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-burgundy/10 pt-4 text-[11px] text-white/80">
              <div>
                <span className="block text-orange font-heading uppercase tracking-wider text-[9px] font-bold">Lifecycle Checkpoints</span>
                <span className="block font-body mt-0.5">60–89 Days: Warning in #leads-council</span>
                <span className="block font-body text-white/60">90+ Days Inactivity: Automated Archival</span>
              </div>
              <div>
                <span className="block text-orange font-heading uppercase tracking-wider text-[9px] font-bold">Active Chapter Nodes</span>
                <span className="block font-body mt-0.5">Delhi · Mumbai · Chennai · Kanpur · Solan</span>
                <span className="block font-body text-white/60">Jaipur · Beawar · Noida · Hyderabad · Kolkata</span>
              </div>
            </div>
          </motion.div>

          {/* Card 3: Voice Channels & AI Transcriber */}
          <motion.div
            initial={{ opacity: 0, x: 40, filter: "blur(10px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.8, delay: 0.7, ease: "easeOut" }}
            whileHover={{ scale: 1.01, backgroundColor: "rgba(151, 25, 44, 0.05)" }}
            className="liquid-glass rounded-[1.25rem] p-6 border border-burgundy/10 cursor-pointer transition-all duration-300"
            id="scheduler-specs"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-[0.5rem] flex items-center justify-center bg-burgundy/20 text-orange shrink-0">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </div>
              <h3 className="font-heading font-bold uppercase tracking-wider text-sm text-white/95">
                AI Voice Channel Transcription
              </h3>
            </div>
            
            <p className="text-xs text-white/70 font-body leading-relaxed mb-4">
              Discord Bot auto-provisions audio VC channels 5 minutes before scheduled meetings. Captures voice recordings, plays English/Hindi consent notices, and generates summaries using Gemini AI.
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-burgundy/10 pt-4 text-[11px] text-white/80">
              <div>
                <span className="block text-orange font-heading uppercase tracking-wider text-[9px] font-bold">Gemini Processing</span>
                <span className="block font-body mt-0.5">Audio transcription parsing</span>
                <span className="block font-body text-white/60">Interactive DM action-item notification</span>
              </div>
              <div>
                <span className="block text-orange font-heading uppercase tracking-wider text-[9px] font-bold">Sync Pipelines</span>
                <span className="block font-body mt-0.5">SQLite/Turso database transaction sync</span>
                <span className="block font-body text-white/60">Fuzzy name mapping to Discord Snowflake IDs</span>
              </div>
            </div>
          </motion.div>

        </div>

      </div>

      {/* Footer Info (just for fun bottom bar) */}
      <footer className="relative z-10 text-center text-[10px] text-white/40 font-heading tracking-widest uppercase mt-8 border-t border-burgundy/10 pt-4 w-full px-4 max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-2">
        <div>GOBITSNBYTES FOUNDATION © 2026 · License Section 8 No. 186266</div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>Next.js 15 + React 19 Dashboard</span>
        </div>
      </footer>
    </section>
  );
}
