"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  FileText,
  Upload,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  ShieldCheck,
  ArrowRight,
  RefreshCw,
  BookOpen,
  Search,
  Plus,
  Clock,
  ExternalLink,
  ChevronRight,
  Inbox,
} from "lucide-react";

interface PipelineContract {
  id: string;
  title: string;
  counterparty: string;
  status: string;
  value?: string;
  signatories_count: number;
  highest_risk: "high" | "medium" | "low" | "none";
  created_at: string;
  days_in_stage: number;
}

export default function ContractAssistantPage() {
  const [contracts, setContracts] = useState<PipelineContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [rulesCount, setRulesCount] = useState<number>(35);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [rulesRes, contractsRes] = await Promise.all([
        fetch("/api/contract-assistant/rules").catch(() => null),
        fetch("/api/contract-assistant/contracts").catch(() => null),
      ]);

      if (rulesRes && rulesRes.ok) {
        const rulesData = await rulesRes.json();
        setRulesCount(rulesData.total_rules || 35);
      }

      if (contractsRes && contractsRes.ok) {
        const contractsData = await contractsRes.json();
        if (Array.isArray(contractsData)) {
          setContracts(contractsData);
        }
      }
    } catch (err) {
      console.error("Failed to load contracts data", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    const uploadedFile = e.target.files[0];

    setAnalyzing(true);
    const formData = new FormData();
    formData.append("file", uploadedFile);

    try {
      const res = await fetch("/api/contract-assistant/analyze", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        await fetchData();
        if (data.contract_id) {
          window.location.href = `/dashboard/contract-assistant/${data.contract_id}`;
        }
      }
    } catch (err) {
      console.error("Analysis error", err);
    } finally {
      setAnalyzing(false);
    }
  };

  const filteredContracts = contracts.filter(
    (c) =>
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.counterparty.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const inReviewContracts = filteredContracts.filter(
    (c) => c.status === "in_review" || c.status === "draft" || c.status === "reviewing"
  );
  const matchedOutForSignature = filteredContracts.filter(
    (c) =>
      c.status === "out_for_signature" ||
      c.status === "pending" ||
      c.status === "pending_signatures" ||
      c.status === "sent" ||
      c.status === "dispatched"
  );
  const dottedContracts = filteredContracts.filter(
    (c) =>
      c.status === "dotted" ||
      c.status === "completed" ||
      c.status === "executed" ||
      c.status === "sealed" ||
      c.status === "signed"
  );

  // Safety fallback to make sure 100% of contracts returned by API appear in the board
  const assignedIds = new Set([
    ...inReviewContracts.map((c) => c.id),
    ...matchedOutForSignature.map((c) => c.id),
    ...dottedContracts.map((c) => c.id),
  ]);
  const unassignedContracts = filteredContracts.filter((c) => !assignedIds.has(c.id));
  const outForSignatureContracts = [...matchedOutForSignature, ...unassignedContracts];

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-main text-main-foreground p-5 rounded-base border-2 border-border shadow-dark flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl sm:text-2xl font-heading font-black tracking-tight uppercase">
              Internal Contract Assistant
            </h1>
            <span className="bg-orange text-black text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-base uppercase tracking-wider border border-black shadow-light">
              LEGAL ENGINE
            </span>
          </div>
          <p className="text-xs text-main-foreground/80 font-base">
            CC <span className="font-mono underline font-bold text-orange">contracts@gobitsnbytes.org</span> or <span className="font-mono underline font-bold text-orange">legal@gobitsnbytes.org</span> to review, redline &amp; dispatch legal agreements.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/dashboard/contract-assistant/rules"
            className="flex items-center gap-1.5 px-4 py-2 bg-secondary-background text-foreground text-xs font-mono font-bold border-2 border-border rounded-base shadow-light hover:bg-muted"
          >
            <BookOpen className="w-3.5 h-3.5 text-orange" /> OKF Rules ({rulesCount})
          </Link>
          <label className="flex items-center gap-1.5 px-4 py-2 bg-orange text-black text-xs font-heading font-black uppercase tracking-wider border-2 border-black rounded-base shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none cursor-pointer transition-all">
            {analyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Upload Contract
            <input type="file" accept=".pdf,.docx" onChange={handleFileUpload} disabled={analyzing} className="hidden" />
          </label>
        </div>
      </div>

      {/* Global Search & Filters */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search active contracts or agreements..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-secondary-background border-2 border-border rounded-base text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-orange shadow-light"
          />
        </div>

        <div className="flex items-center gap-4 text-xs font-mono font-bold text-muted-foreground">
          <span>{contracts.length} Total Contracts</span>
          <span>&bull;</span>
          <span className="text-orange">{inReviewContracts.length} In Review</span>
        </div>
      </div>

      {/* Kanban Pipeline Board */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Column 1: In Review */}
        <div className="bg-secondary-background border-2 border-border rounded-base p-4 shadow-dark space-y-4">
          <div className="flex items-center justify-between border-b-2 border-border pb-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-base bg-main border border-border" />
              <h2 className="text-xs font-heading font-black uppercase tracking-wider text-foreground">In Review</h2>
            </div>
            <span className="px-2 py-0.5 bg-main text-white border border-border rounded-base text-[10px] font-mono font-bold">
              {inReviewContracts.length}
            </span>
          </div>

          <div className="space-y-3">
            {inReviewContracts.length === 0 ? (
              <div className="bg-muted border-2 border-dashed border-border rounded-base p-6 text-center text-xs text-muted-foreground font-mono">
                <Inbox className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
                No contracts currently in review.
              </div>
            ) : (
              inReviewContracts.map((c) => (
                <div
                  key={c.id}
                  className="bg-muted border-2 border-border rounded-base p-4 shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-xs text-foreground line-clamp-1">{c.title}</h3>
                    <span className="px-2 py-0.5 bg-amber-950 text-amber-400 text-[10px] font-mono font-bold rounded-base border border-amber-800 shrink-0">
                      Reviewing
                    </span>
                  </div>

                  <p className="text-[11px] text-muted-foreground font-mono">{c.counterparty}</p>

                  <div className="flex items-center justify-between text-[10px] font-mono font-bold text-foreground pt-2 border-t border-border">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-zinc-500" /> {c.days_in_stage}d in review
                    </span>
                    <Link
                      href={`/dashboard/contract-assistant/${c.id}`}
                      className="text-orange hover:underline flex items-center gap-0.5"
                    >
                      Audit <ChevronRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 2: Out for Signature */}
        <div className="bg-secondary-background border-2 border-border rounded-base p-4 shadow-dark space-y-4">
          <div className="flex items-center justify-between border-b-2 border-border pb-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-base bg-orange border border-black" />
              <h2 className="text-xs font-heading font-black uppercase tracking-wider text-foreground">Out for Signature</h2>
            </div>
            <span className="px-2 py-0.5 bg-orange text-black border border-black rounded-base text-[10px] font-mono font-bold">
              {outForSignatureContracts.length}
            </span>
          </div>

          <div className="space-y-3">
            {outForSignatureContracts.length === 0 ? (
              <div className="bg-muted border-2 border-dashed border-border rounded-base p-6 text-center text-xs text-muted-foreground font-mono">
                <Clock className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
                No active signature dispatches pending.
              </div>
            ) : (
              outForSignatureContracts.map((c) => (
                <div
                  key={c.id}
                  className="bg-muted border-2 border-border rounded-base p-4 shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-xs text-foreground line-clamp-1">{c.title}</h3>
                    <span className="px-2 py-0.5 bg-orange/20 text-orange text-[10px] font-mono font-bold rounded-base border border-orange/40 shrink-0">
                      Dispatched
                    </span>
                  </div>

                  <p className="text-[11px] text-muted-foreground font-mono">{c.counterparty}</p>

                  <div className="flex items-center justify-between text-[10px] font-mono font-bold text-foreground pt-2 border-t border-border">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-orange" /> {c.signatories_count} signatories
                    </span>
                    <Link
                      href={`/dashboard/contract-assistant/${c.id}`}
                      className="text-orange hover:underline flex items-center gap-0.5"
                    >
                      Status <ChevronRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 3: Dotted & Executed */}
        <div className="bg-secondary-background border-2 border-border rounded-base p-4 shadow-dark space-y-4">
          <div className="flex items-center justify-between border-b-2 border-border pb-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-base bg-emerald-500 border border-border" />
              <h2 className="text-xs font-heading font-black uppercase tracking-wider text-foreground">Dotted &amp; Executed</h2>
            </div>
            <span className="px-2 py-0.5 bg-emerald-950 border border-emerald-800 rounded-base text-[10px] font-mono font-bold text-emerald-400">
              {dottedContracts.length}
            </span>
          </div>

          <div className="space-y-3">
            {dottedContracts.length === 0 ? (
              <div className="bg-muted border-2 border-dashed border-border rounded-base p-6 text-center text-xs text-muted-foreground font-mono">
                <ShieldCheck className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
                No fully executed contracts archived yet.
              </div>
            ) : (
              dottedContracts.map((c) => (
                <div
                  key={c.id}
                  className="bg-muted border-2 border-border rounded-base p-4 shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-xs text-foreground line-clamp-1">{c.title}</h3>
                    <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 text-[10px] font-mono font-bold rounded-base border border-emerald-800 shrink-0">
                      Executed
                    </span>
                  </div>

                  <p className="text-[11px] text-muted-foreground font-mono">{c.counterparty}</p>

                  <div className="flex items-center justify-between text-[10px] font-mono font-bold pt-2 border-t border-border">
                    <span className="flex items-center gap-1 text-emerald-400">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Sealed (SHA-256)
                    </span>
                    <Link
                      href={`/verify/${c.id}`}
                      className="text-orange hover:underline flex items-center gap-0.5"
                    >
                      Certificate <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
