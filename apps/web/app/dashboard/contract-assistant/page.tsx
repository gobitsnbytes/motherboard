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
  status: "in_review" | "out_for_signature" | "dotted";
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
      const [rulesRes, requestsRes] = await Promise.all([
        fetch("/api/contract-assistant/rules").catch(() => null),
        fetch("/api/signatures/requests").catch(() => null),
      ]);

      if (rulesRes && rulesRes.ok) {
        const rulesData = await rulesRes.json();
        setRulesCount(rulesData.total_rules || 35);
      }

      if (requestsRes && requestsRes.ok) {
        const requestsData = await requestsRes.json();
        if (Array.isArray(requestsData)) {
          const mapped: PipelineContract[] = requestsData.map((req: any) => ({
            id: req.id,
            title: req.title,
            counterparty: req.recipients?.[0]?.name || "Internal Legal",
            status: req.status === "completed" ? "dotted" : req.status === "pending" ? "out_for_signature" : "in_review",
            value: "Official Contract",
            signatories_count: req.recipients?.length || 1,
            highest_risk: "none",
            created_at: req.created_at || new Date().toISOString(),
            days_in_stage: Math.floor((Date.now() - new Date(req.created_at || Date.now()).getTime()) / 86400000),
          }));
          setContracts(mapped);
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
        const newContract: PipelineContract = {
          id: data.contract_id || `cntr_${Date.now()}`,
          title: data.title || uploadedFile.name,
          counterparty: "Pending Review",
          status: "in_review",
          value: "Under Audit",
          signatories_count: 2,
          highest_risk: data.high_risks > 0 ? "high" : data.medium_risks > 0 ? "medium" : "low",
          created_at: new Date().toISOString(),
          days_in_stage: 0,
        };
        setContracts((prev) => [newContract, ...prev]);
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

  const inReviewContracts = filteredContracts.filter((c) => c.status === "in_review");
  const outForSignatureContracts = filteredContracts.filter((c) => c.status === "out_for_signature");
  const dottedContracts = filteredContracts.filter((c) => c.status === "dotted");

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-[#3C0A12] text-white p-6 rounded-2xl border-2 border-[#120F0A] shadow-[6px_6px_0px_0px_#120F0A] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl sm:text-2xl font-black font-sans">
              Internal Contract Assistant
            </h1>
            <span className="bg-[#FC920D] text-[#120F0A] text-[10px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              Legal Engine
            </span>
          </div>
          <p className="text-xs text-[#FED39E] font-medium">
            CC <span className="font-mono underline font-bold">contracts@gobitsnbytes.org</span> or <span className="font-mono underline font-bold">legal@gobitsnbytes.org</span> to review, redline &amp; dispatch legal agreements.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/dashboard/contract-assistant/rules"
            className="flex items-center gap-1.5 px-4 py-2 bg-white text-[#120F0A] text-xs font-bold border-2 border-[#120F0A] rounded-xl shadow-[2px_2px_0px_0px_#120F0A] hover:bg-gray-100"
          >
            <BookOpen className="w-3.5 h-3.5 text-[#97192C]" /> OKF Rules ({rulesCount})
          </Link>
          <label className="flex items-center gap-1.5 px-4 py-2 bg-[#FC920D] text-[#120F0A] text-xs font-black border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-1px] cursor-pointer transition-all">
            {analyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Upload Contract
            <input type="file" accept=".pdf,.docx" onChange={handleFileUpload} disabled={analyzing} className="hidden" />
          </label>
        </div>
      </div>

      {/* Global Search & Filters */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#716F6C]" />
          <input
            type="text"
            placeholder="Search active contracts or agreements..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#97192C] shadow-[2px_2px_0px_0px_#120F0A]"
          />
        </div>

        <div className="flex items-center gap-4 text-xs font-bold text-[#716F6C]">
          <span>{contracts.length} Total Contracts</span>
          <span>•</span>
          <span className="text-[#97192C]">{inReviewContracts.length} In Review</span>
        </div>
      </div>

      {/* Kanban Pipeline Board */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Column 1: In Review */}
        <div className="bg-[#FAF8F5] border-2 border-[#120F0A] rounded-2xl p-4 shadow-[4px_4px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#97192C]" />
              <h2 className="text-xs font-black uppercase tracking-wider text-[#120F0A]">In Review</h2>
            </div>
            <span className="px-2 py-0.5 bg-[#FEE9CF] border border-[#120F0A] rounded-md text-[10px] font-bold">
              {inReviewContracts.length}
            </span>
          </div>

          <div className="space-y-3">
            {inReviewContracts.length === 0 ? (
              <div className="bg-white border-2 border-dashed border-[#D0CFCE] rounded-xl p-6 text-center text-xs text-[#716F6C]">
                <Inbox className="w-6 h-6 mx-auto mb-2 text-[#A09F9D]" />
                No contracts currently in review.
              </div>
            ) : (
              inReviewContracts.map((c) => (
                <div
                  key={c.id}
                  className="bg-white border-2 border-[#120F0A] rounded-xl p-4 shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-2px] transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-xs text-[#120F0A] line-clamp-1">{c.title}</h3>
                    <span className="px-2 py-0.5 bg-[#FEE9CF] text-[#120F0A] text-[10px] font-bold rounded border border-[#120F0A]">
                      Reviewing
                    </span>
                  </div>

                  <p className="text-[11px] text-[#716F6C] font-medium">{c.counterparty}</p>

                  <div className="flex items-center justify-between text-[10px] font-bold text-[#413F3B] pt-2 border-t border-gray-100">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-[#716F6C]" /> {c.days_in_stage}d in review
                    </span>
                    <Link
                      href={`/dashboard/contract-assistant/${c.id}`}
                      className="text-[#97192C] hover:underline flex items-center gap-0.5"
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
        <div className="bg-[#FAF8F5] border-2 border-[#120F0A] rounded-2xl p-4 shadow-[4px_4px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#FC920D]" />
              <h2 className="text-xs font-black uppercase tracking-wider text-[#120F0A]">Out for Signature</h2>
            </div>
            <span className="px-2 py-0.5 bg-[#FEE9CF] border border-[#120F0A] rounded-md text-[10px] font-bold">
              {outForSignatureContracts.length}
            </span>
          </div>

          <div className="space-y-3">
            {outForSignatureContracts.length === 0 ? (
              <div className="bg-white border-2 border-dashed border-[#D0CFCE] rounded-xl p-6 text-center text-xs text-[#716F6C]">
                <Clock className="w-6 h-6 mx-auto mb-2 text-[#A09F9D]" />
                No active signature dispatches pending.
              </div>
            ) : (
              outForSignatureContracts.map((c) => (
                <div
                  key={c.id}
                  className="bg-white border-2 border-[#120F0A] rounded-xl p-4 shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-2px] transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-xs text-[#120F0A] line-clamp-1">{c.title}</h3>
                    <span className="px-2 py-0.5 bg-[#FED39E] text-[#120F0A] text-[10px] font-bold rounded border border-[#120F0A]">
                      Dispatched
                    </span>
                  </div>

                  <p className="text-[11px] text-[#716F6C] font-medium">{c.counterparty}</p>

                  <div className="flex items-center justify-between text-[10px] font-bold text-[#413F3B] pt-2 border-t border-gray-100">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-[#FC920D]" /> {c.signatories_count} signatories
                    </span>
                    <Link
                      href={`/dashboard/contract-assistant/${c.id}`}
                      className="text-[#97192C] hover:underline flex items-center gap-0.5"
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
        <div className="bg-[#FAF8F5] border-2 border-[#120F0A] rounded-2xl p-4 shadow-[4px_4px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-3">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-500" />
              <h2 className="text-xs font-black uppercase tracking-wider text-[#120F0A]">Dotted &amp; Executed</h2>
            </div>
            <span className="px-2 py-0.5 bg-emerald-100 border border-[#120F0A] rounded-md text-[10px] font-bold text-emerald-800">
              {dottedContracts.length}
            </span>
          </div>

          <div className="space-y-3">
            {dottedContracts.length === 0 ? (
              <div className="bg-white border-2 border-dashed border-[#D0CFCE] rounded-xl p-6 text-center text-xs text-[#716F6C]">
                <ShieldCheck className="w-6 h-6 mx-auto mb-2 text-[#A09F9D]" />
                No fully executed contracts archived yet.
              </div>
            ) : (
              dottedContracts.map((c) => (
                <div
                  key={c.id}
                  className="bg-white border-2 border-[#120F0A] rounded-xl p-4 shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-2px] transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-xs text-[#120F0A] line-clamp-1">{c.title}</h3>
                    <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded border border-[#120F0A]">
                      Executed
                    </span>
                  </div>

                  <p className="text-[11px] text-[#716F6C] font-medium">{c.counterparty}</p>

                  <div className="flex items-center justify-between text-[10px] font-bold text-[#413F3B] pt-2 border-t border-gray-100">
                    <span className="flex items-center gap-1 text-emerald-600 font-bold">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Sealed (SHA-256)
                    </span>
                    <Link
                      href={`/verify/${c.id}`}
                      className="text-[#97192C] hover:underline flex items-center gap-0.5"
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
