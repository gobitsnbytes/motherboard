"use client";

import React from "react";
import { ShieldCheck, Lock, Building2, HeartHandshake } from "lucide-react";
import { Badge } from "@bnb/ui";

export default function DashboardFooter() {
  return (
    <footer className="mt-12 border-t-2 border-[#120f0a] bg-[#d0cfce] p-6 text-[#120f0a]">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Top Header Row */}
        <div className="flex flex-col gap-4 border-b-2 border-[#120f0a] pb-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <img
              src="https://gobitsnbytes.org/logo"
              alt="bits&bytes™ logo"
              className="h-6 w-auto select-none"
            />
            <div>
              <h2 className="font-heading text-sm font-black uppercase tracking-wider text-[#120f0a]">
                GOBITSNBYTES FOUNDATION
              </h2>
              <p className="font-base text-xs text-[#413f3b]">
                Independent Teen-Led Builder Network &amp; Section 8 Non-Profit Corporation
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-base border-2 border-[#120f0a] bg-white px-2.5 py-0.5 font-mono text-[11px] font-bold text-[#97192c]">
              Section 8 License #186266
            </span>
            <span className="rounded-base border-2 border-[#120f0a] bg-[#97192c] px-2.5 py-0.5 font-mono text-[11px] font-bold text-white">
              Inc. 2 June 2026
            </span>
            <span className="rounded-base border-2 border-[#120f0a] bg-white px-2.5 py-0.5 font-mono text-[11px] font-bold text-[#413f3b]">
              POCSO &amp; DPDP Compliant
            </span>
          </div>
        </div>

        {/* 2-Column Responsive Grid for Compliance & Disclosures */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs font-base">
          {/* Column 1: Legal Entity & Section 8 Non-Profit Disclosure */}
          <div className="space-y-2.5 rounded-base border-2 border-[#120f0a] bg-white p-4">
            <div className="flex items-center gap-2 font-heading text-xs font-black uppercase tracking-wide text-[#120f0a]">
              <Building2 className="size-4 text-[#fc920d]" />
              <span>Section 8 Non-Profit Disclosure</span>
            </div>
            <p className="leading-relaxed text-[#413f3b]">
              <strong className="text-[#120f0a]">GOBITSNBYTES FOUNDATION</strong> is a registered not-for-profit company under Section 8 of the Companies Act, 2013 (State of Uttar Pradesh, India). Company limited by guarantee without share capital.
            </p>
            <p className="text-[11px] leading-relaxed text-[#716f6c]">
              All income and operational revenues are applied solely towards promoting educational programs, student hackathons, open-source tech initiatives, and charitable objects. No dividend or profit distribution is permitted to legal members or executive officers.
            </p>
          </div>

          {/* Column 2: Minor Safeguarding (POCSO) & Data Privacy (DPDP) */}
          <div className="space-y-2.5 rounded-base border-2 border-[#120f0a] bg-white p-4">
            <div className="flex items-center gap-2 font-heading text-xs font-black uppercase tracking-wide text-[#120f0a]">
              <ShieldCheck className="size-4 text-[#fc920d]" />
              <span>POCSO &amp; DPDP Statutory Compliance</span>
            </div>
            <p className="leading-relaxed text-[#413f3b]">
              <strong className="text-[#120f0a]">Minor Safeguarding (POCSO Act, 2012):</strong> All events and community spaces strictly comply with safeguarding rules. Mandatory parent/guardian consent is required for minor participation. Zero unsupervised adult-minor contact is enforced across all network programs.
            </p>
            <p className="flex items-center justify-between gap-2 border-t border-[#d0cfce] pt-1 text-[11px] leading-relaxed text-[#716f6c]">
              <span className="flex items-center gap-1.5">
                <Lock className="inline size-3 shrink-0 text-[#97192c]" />
                <span>DPDP Act 2023 Encrypted Processing</span>
              </span>
              <a
                href="mailto:hello@gobitsnbytes.org"
                className="font-bold text-[#97192c] hover:underline"
              >
                Safeguarding Escalations &rarr;
              </a>
            </p>
          </div>
        </div>

        {/* Bottom Line */}
        <div className="flex flex-col items-center justify-between border-t-2 border-[#120f0a] pt-3 font-mono text-[11px] text-[#413f3b] sm:flex-row">
          <p>&copy; {new Date().getFullYear()} GOBITSNBYTES FOUNDATION. All rights reserved.</p>
          <p className="mt-1 sm:mt-0">bits&bytes™ is an independent student-led builder network.</p>
        </div>
      </div>
    </footer>
  );
}
