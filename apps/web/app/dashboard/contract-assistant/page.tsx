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
  FileCode,
  RefreshCw,
  Send,
  HelpCircle,
  Zap,
  BookOpen,
} from "lucide-react";

interface ClauseIssue {
  clause_ref: string;
  heading: string;
  text: string;
  has_risk: boolean;
  risk_type: string;
  severity: string;
  source: string;
  plain_english: string;
  suggested_action: string;
  policy_link?: string;
  template_fix?: string;
  tier: number;
}

interface ContractAnalysis {
  contract_id: string;
  filename: string;
  title: string;
  total_clauses: number;
  high_risks: number;
  medium_risks: number;
  low_risks: number;
  page_count: number;
  previews: string[];
  issues: ClauseIssue[];
  created_at: string;
}

export default function ContractAssistantPage() {
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<ContractAnalysis | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<ClauseIssue | null>(null);
  const [autofixLoading, setAutofixLoading] = useState(false);
  const [autofixResult, setAutofixResult] = useState<{
    tier: number;
    original: string;
    rewrite: string;
    rationale: string;
  } | null>(null);
  const [rulesCount, setRulesCount] = useState<number>(0);

  useEffect(() => {
    fetch("/api/contract-assistant/rules")
      .then((res) => res.json())
      .then((data) => setRulesCount(data.total_rules || 0))
      .catch(() => setRulesCount(3));
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    const uploadedFile = e.target.files[0];
    setFile(uploadedFile);

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
        setAnalysis(data);
        if (data.issues && data.issues.length > 0) {
          setSelectedIssue(data.issues[0]);
        }
      } else {
        alert("Failed to analyze contract. Please check file format.");
      }
    } catch (err) {
      console.error("Analysis error", err);
      alert("Error contacting Contract Assistant server.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerateAutofix = async (issue: ClauseIssue) => {
    setAutofixLoading(true);
    setAutofixResult(null);

    try {
      const res = await fetch("/api/contract-assistant/autofix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clause_text: issue.text,
          issue_description: issue.plain_english,
          tier: issue.tier,
          policy_tag: issue.severity === "high" ? "liability" : "payment",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setAutofixResult({
          tier: data.tier,
          original: data.original_clause,
          rewrite: data.suggested_rewrite,
          rationale: data.rationale,
        });
      }
    } catch (err) {
      console.error("Autofix error", err);
    } finally {
      setAutofixLoading(false);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl sm:text-2xl font-black text-[#120F0A] font-sans">
              Internal Contract Assistant
            </h1>
            <span className="bg-[#97192C] text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              Legal Due Diligence
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#716F6C] font-medium">
            AI-powered risk review, OKF due-diligence rule engine, &amp; automated redlining ({" "}
            <span className="font-mono text-[#97192C] font-bold">legal@gobitsnbytes.org</span> )
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="bg-[#FED39E] text-[#120F0A] text-xs font-bold px-3 py-1.5 rounded-xl border border-[#120F0A] flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#97192C]" /> SparkCloud AI (auto)
          </div>
          <div className="bg-emerald-50 text-emerald-800 text-xs font-bold px-3 py-1.5 rounded-xl border border-emerald-300 flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-emerald-600" /> OKF Rules Active ({rulesCount})
          </div>
        </div>
      </div>

      {/* Contract Upload & Pipeline State */}
      {!analysis && (
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] text-center space-y-6">
          <div className="max-w-md mx-auto space-y-3">
            <div className="w-16 h-16 bg-[#FEE9CF] rounded-2xl border-2 border-[#120F0A] flex items-center justify-center mx-auto shadow-[2px_2px_0px_0px_#120F0A]">
              <Upload className="w-8 h-8 text-[#97192C]" />
            </div>
            <h2 className="text-lg font-black text-[#120F0A]">Upload Contract for AI &amp; OKF Due Diligence</h2>
            <p className="text-xs text-[#716F6C]">
              Supports <span className="font-bold text-[#120F0A]">.pdf</span> and{" "}
              <span className="font-bold text-[#120F0A]">.docx</span> files. Or forward contracts directly to{" "}
              <span className="font-mono font-bold text-[#97192C]">contracts@gobitsnbytes.org</span>.
            </p>
          </div>

          <label className="inline-flex items-center gap-2 bg-[#97192C] text-white px-6 py-3 rounded-xl font-bold text-sm cursor-pointer shadow-[3px_3px_0px_0px_#120F0A] hover:translate-x-[1px] hover:translate-y-[1px] transition-all">
            {analyzing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" /> Analyzing Document...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4" /> Select Contract File
              </>
            )}
            <input type="file" accept=".pdf,.docx" onChange={handleFileUpload} disabled={analyzing} className="hidden" />
          </label>
        </div>
      )}

      {/* Analysis Results View */}
      {analysis && (
        <div className="space-y-6">
          {/* Executive Metrics Overview */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl shadow-[3px_3px_0px_0px_#120F0A]">
              <div className="text-xs text-[#716F6C] font-bold uppercase">Total Clauses</div>
              <div className="text-2xl font-black text-[#120F0A]">{analysis.total_clauses}</div>
            </div>

            <div className="bg-red-50 border-2 border-red-900 p-4 rounded-xl shadow-[3px_3px_0px_0px_#97192C]">
              <div className="text-xs text-red-700 font-bold uppercase flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> High Risk
              </div>
              <div className="text-2xl font-black text-red-900">{analysis.high_risks}</div>
            </div>

            <div className="bg-amber-50 border-2 border-amber-800 p-4 rounded-xl shadow-[3px_3px_0px_0px_#D46846]">
              <div className="text-xs text-amber-700 font-bold uppercase">Medium Risk</div>
              <div className="text-2xl font-black text-amber-900">{analysis.medium_risks}</div>
            </div>

            <div className="bg-emerald-50 border-2 border-emerald-800 p-4 rounded-xl shadow-[3px_3px_0px_0px_#059669]">
              <div className="text-xs text-emerald-700 font-bold uppercase flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> OKF Verified
              </div>
              <div className="text-2xl font-black text-emerald-900">
                {analysis.total_clauses - analysis.high_risks - analysis.medium_risks}
              </div>
            </div>
          </div>

          {/* Main Two-Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Clause & Issues List */}
            <div className="lg:col-span-6 space-y-4">
              <div className="bg-white border-2 border-[#120F0A] p-4 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A]">
                <h3 className="text-sm font-black text-[#120F0A] uppercase tracking-wider mb-3">
                  Clause-by-Clause Findings ({analysis.issues.length})
                </h3>

                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
                  {analysis.issues.map((issue, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setSelectedIssue(issue);
                        setAutofixResult(null);
                      }}
                      className={`p-3.5 rounded-xl border-2 cursor-pointer transition-all ${
                        selectedIssue?.clause_ref === issue.clause_ref
                          ? "bg-[#FEE9CF] border-[#120F0A] shadow-[2px_2px_0px_0px_#120F0A]"
                          : "bg-gray-50 border-gray-200 hover:border-[#120F0A]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="font-mono text-xs font-black text-[#97192C]">{issue.clause_ref}</span>
                        <div className="flex items-center gap-1.5">
                          {issue.source === "rule_engine" ? (
                            <span className="bg-blue-100 text-blue-800 text-[10px] font-bold px-2 py-0.5 rounded border border-blue-300">
                              ⚡ OKF Rule
                            </span>
                          ) : (
                            <span className="bg-purple-100 text-purple-800 text-[10px] font-bold px-2 py-0.5 rounded border border-purple-300">
                              ✨ AI Pass
                            </span>
                          )}

                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                              issue.severity === "high"
                                ? "bg-red-100 text-red-800"
                                : issue.severity === "medium"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {issue.severity}
                          </span>
                        </div>
                      </div>

                      <div className="text-xs font-bold text-[#120F0A] mb-1">{issue.heading}</div>
                      <p className="text-xs text-[#716F6C] line-clamp-2">{issue.plain_english}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Selected Clause Detail & Auto-Fix Panel */}
            <div className="lg:col-span-6 space-y-4">
              {selectedIssue ? (
                <div className="bg-white border-2 border-[#120F0A] p-5 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] space-y-4">
                  <div className="flex items-center justify-between border-b pb-3 border-gray-200">
                    <div>
                      <span className="font-mono text-xs font-black text-[#97192C]">{selectedIssue.clause_ref}</span>
                      <h3 className="text-base font-black text-[#120F0A]">{selectedIssue.heading}</h3>
                    </div>
                    <span className="text-xs font-bold bg-[#3C0A12] text-white px-2.5 py-1 rounded-lg">
                      Tier {selectedIssue.tier} {selectedIssue.tier === 1 ? "Template Swap" : "AI Redline"}
                    </span>
                  </div>

                  {/* Clause Text */}
                  <div>
                    <label className="text-[11px] font-bold uppercase text-[#716F6C] block mb-1">Original Clause Text</label>
                    <div className="p-3 bg-gray-50 border rounded-xl text-xs text-[#120F0A] font-mono leading-relaxed">
                      "{selectedIssue.text}"
                    </div>
                  </div>

                  {/* Risk Explanation */}
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-1">
                    <span className="text-[11px] font-bold text-amber-900 uppercase flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-700" /> Risk Finding
                    </span>
                    <p className="text-xs text-amber-900 font-medium">{selectedIssue.plain_english}</p>
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 flex flex-wrap gap-2">
                    <button
                      onClick={() => handleGenerateAutofix(selectedIssue)}
                      disabled={autofixLoading}
                      className="bg-[#97192C] text-white px-4 py-2 rounded-xl text-xs font-bold shadow-[2px_2px_0px_0px_#120F0A] hover:translate-x-[1px] hover:translate-y-[1px] flex items-center gap-1.5"
                    >
                      {autofixLoading ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Zap className="w-3.5 h-3.5 text-[#FC920D]" />
                      )}
                      Generate Tier-{selectedIssue.tier} Fix
                    </button>

                    <Link
                      href="/dashboard/signatures/builder"
                      className="bg-white border-2 border-[#120F0A] text-[#120F0A] px-4 py-2 rounded-xl text-xs font-bold shadow-[2px_2px_0px_0px_#120F0A] flex items-center gap-1.5"
                    >
                      <Send className="w-3.5 h-3.5 text-[#97192C]" /> Dispatch to e-Signature
                    </Link>
                  </div>

                  {/* Auto-Fix Result Redline Diff */}
                  {autofixResult && (
                    <div className="mt-4 p-4 bg-emerald-50 border-2 border-emerald-700 rounded-xl space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-emerald-900 flex items-center gap-1">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          Proposed Redline Revision (Tier {autofixResult.tier})
                        </span>
                      </div>

                      <div className="space-y-2">
                        <div>
                          <span className="text-[10px] font-bold text-emerald-800 uppercase block">Suggested Text</span>
                          <div className="p-3 bg-white border border-emerald-300 rounded-lg text-xs font-mono text-emerald-950 font-bold">
                            {autofixResult.rewrite}
                          </div>
                        </div>

                        <p className="text-[11px] text-emerald-800 italic">
                          Rationale: {autofixResult.rationale}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-white border-2 border-dashed border-gray-300 p-8 rounded-2xl text-center text-gray-400 text-xs font-medium">
                  Select a clause on the left to view detailed risk analysis and redline options.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
