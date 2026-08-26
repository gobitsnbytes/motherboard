"use client";

import React from "react";
import { ShieldCheck, Lock, Building2, HeartHandshake } from "lucide-react";
import { Badge } from "@bnb/ui";

export default function DashboardFooter() {
  return (
    <footer className="mt-12 border-t-2 border-border bg-[#0d0d10] p-6 text-foreground">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Top Header Row */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b-2 border-border pb-4">
          <div className="flex items-center gap-3">
            <img
              src="https://gobitsnbytes.org/logo"
              alt="bits&bytes logo"
              className="h-6 w-auto select-none"
            />
            <div>
              <h2 className="font-heading font-black text-sm uppercase tracking-wider text-white">
                GOBITSNBYTES FOUNDATION
              </h2>
              <p className="text-xs text-zinc-300 font-base">
                Independent Teen-Led Builder Network &amp; Section 8 Non-Profit Corporation
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="border-2 border-border bg-[#181820] text-orange px-2.5 py-0.5 text-[11px] font-mono font-bold rounded-base shadow-light">
              Section 8 License #186266
            </span>
            <span className="border-2 border-border bg-main text-white px-2.5 py-0.5 text-[11px] font-mono font-bold rounded-base shadow-light">
              Inc. 2 June 2026
            </span>
            <span className="border-2 border-border bg-[#181820] text-emerald-400 px-2.5 py-0.5 text-[11px] font-mono font-bold rounded-base shadow-light">
              POCSO &amp; DPDP Compliant
            </span>
          </div>
        </div>

        {/* 2-Column Responsive Grid for Compliance & Disclosures */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs font-base">
          {/* Column 1: Legal Entity & Section 8 Non-Profit Disclosure */}
          <div className="rounded-base border-2 border-border bg-[#141418] p-4 space-y-2.5 shadow-light">
            <div className="flex items-center gap-2 text-white font-heading font-black text-xs uppercase tracking-wide">
              <Building2 className="size-4 text-orange" />
              <span>Section 8 Non-Profit Disclosure</span>
            </div>
            <p className="leading-relaxed text-zinc-300">
              <strong className="text-white">GOBITSNBYTES FOUNDATION</strong> is a registered not-for-profit company under Section 8 of the Companies Act, 2013 (State of Uttar Pradesh, India). Company limited by guarantee without share capital.
            </p>
            <p className="leading-relaxed text-[11px] text-zinc-400">
              All income and operational revenues are applied solely towards promoting educational programs, student hackathons, open-source tech initiatives, and charitable objects. No dividend or profit distribution is permitted to legal members or executive officers.
            </p>
          </div>

          {/* Column 2: Minor Safeguarding (POCSO) & Data Privacy (DPDP) */}
          <div className="rounded-base border-2 border-border bg-[#141418] p-4 space-y-2.5 shadow-light">
            <div className="flex items-center gap-2 text-white font-heading font-black text-xs uppercase tracking-wide">
              <ShieldCheck className="size-4 text-orange" />
              <span>POCSO &amp; DPDP Statutory Compliance</span>
            </div>
            <p className="leading-relaxed text-zinc-300">
              <strong className="text-white">Minor Safeguarding (POCSO Act, 2012):</strong> All events and community spaces strictly comply with safeguarding rules. Mandatory parent/guardian consent is required for minor participation. Zero unsupervised adult-minor contact is enforced across all network programs.
            </p>
            <p className="leading-relaxed text-[11px] text-zinc-400 flex items-center justify-between gap-2 pt-1 border-t border-border">
              <span className="flex items-center gap-1.5">
                <Lock className="size-3 text-emerald-400 inline shrink-0" />
                <span>DPDP Act 2023 Encrypted Processing</span>
              </span>
              <a
                href="mailto:hello@gobitsnbytes.org"
                className="text-orange hover:underline font-bold"
              >
                Safeguarding Escalations &rarr;
              </a>
            </p>
          </div>
        </div>

        {/* Bottom Line */}
        <div className="flex flex-col sm:flex-row items-center justify-between text-[11px] text-zinc-400 font-mono border-t-2 border-border pt-3">
          <p>&copy; {new Date().getFullYear()} GOBITSNBYTES FOUNDATION. All rights reserved.</p>
          <p className="mt-1 sm:mt-0">bits&bytes™ is an independent student-led builder network.</p>
        </div>
      </div>
    </footer>
  );
}

