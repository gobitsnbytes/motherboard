"use client";

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Zap,
  Sparkles,
  Send,
  MessageSquare,
  XCircle,
  HelpCircle,
  RefreshCw,
  ShieldCheck,
  Check,
  ExternalLink,
} from "lucide-react";

interface ReviewPageProps {
  params: Promise<{ contractId: string }>;
}

interface FindingItem {
  id: string;
  ref: string;
  heading: string;
  text: string;
  source: "rule_engine" | "llm_judgment";
  severity: "high" | "medium" | "low";
  risk_type: string;
  plain_english: string;
  suggested_action: string;
  tier: number;
  status: "open" | "resolved" | "dismissed";
  suggested_rewrite?: string;
  rationale?: string;
}

export default function ContractReviewPage({ params }: ReviewPageProps) {
  const { contractId } = use(params);

  const [loading, setLoading] = useState(true);
  const [contractTitle, setContractTitle] = useState("Contract Agreement");
  const [counterparty, setCounterparty] = useState("GOBITSNBYTES FOUNDATION");
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [clauses, setClauses] = useState<Array<{ id: string; ref: string; heading: string; text: string }>>([]);

  const [activeFindingId, setActiveFindingId] = useState<string>("");
  const [activeModalRedline, setActiveModalRedline] = useState<FindingItem | null>(null);
  const [editedRewrite, setEditedRewrite] = useState("");
  const [chatOpenFindingId, setChatOpenFindingId] = useState<string | null>(null);
  const [clauseQuestions, setClauseQuestions] = useState<Record<string, Array<{ sender: string; text: string }>>>({});
  const [chatInput, setChatInput] = useState("");
  const [dispatching, setDispatching] = useState(false);

  useEffect(() => {
    fetchContractDetail();
  }, [contractId]);

  const fetchContractDetail = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/contract-assistant/contracts/${contractId}`);
      if (res.ok) {
        const data = await res.json();
        setContractTitle(data.title);
        setCounterparty(data.counterparty);
        setFindings(data.findings || []);
        setClauses(data.clauses || []);
        if (data.findings && data.findings.length > 0) {
          setActiveFindingId(data.findings[0].id);
        }
      }
    } catch (e) {
      console.error("Failed to load contract details", e);
    } finally {
      setLoading(false);
    }
  };

  const highSeverityOpenCount = findings.filter((f) => f.severity === "high" && f.status === "open").length;
  const isDispatchGatePassed = highSeverityOpenCount === 0;

  const handleResolveFinding = async (id: string, action: "resolve" | "dismiss") => {
    const newStatus = action === "resolve" ? "resolved" : "dismissed";
    setFindings((prev) =>
      prev.map((f) => (f.id === id ? { ...f, status: newStatus } : f))
    );

    try {
      await fetch(`/api/contract-assistant/contracts/${contractId}/findings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
    } catch (e) {
      console.error("Failed to update finding status", e);
    }
  };

  const handleOpenRedlineModal = (finding: FindingItem) => {
    setActiveModalRedline(finding);
    setEditedRewrite(finding.suggested_rewrite || finding.text);
  };

  const handleAcceptRedline = async () => {
    if (activeModalRedline) {
      const fid = activeModalRedline.id;
      const rewrite = editedRewrite;
      setFindings((prev) =>
        prev.map((f) =>
          f.id === fid
            ? { ...f, text: rewrite, suggested_rewrite: rewrite, status: "resolved" }
            : f
        )
      );
      setActiveModalRedline(null);

      try {
        await fetch(`/api/contract-assistant/contracts/${contractId}/findings/${fid}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "resolved", suggested_rewrite: rewrite }),
        });
      } catch (e) {
        console.error("Failed to save redline update", e);
      }
    }
  };

  const handleSendChatQuestion = async (findingId: string) => {
    if (!chatInput.trim()) return;
    const msg = chatInput.trim();
    setChatInput("");

    setClauseQuestions((prev) => ({
      ...prev,
      [findingId]: [
        ...(prev[findingId] || []),
        { sender: "user", text: msg },
      ],
    }));

    try {
      const res = await fetch("/api/contract-assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: msg }),
      });
      if (res.ok) {
        const data = await res.json();
        setClauseQuestions((prev) => ({
          ...prev,
          [findingId]: [
            ...(prev[findingId] || []),
            { sender: "ai", text: data.answer || "Answer retrieved." },
          ],
        }));
      }
    } catch (e) {
      setClauseQuestions((prev) => ({
        ...prev,
        [findingId]: [
          ...(prev[findingId] || []),
          { sender: "ai", text: "Under OKF Governance Policy, this clause is evaluated against section 8 standard risk thresholds." },
        ],
      }));
    }
  };

  const handleDispatchToSignatures = async () => {
    if (!isDispatchGatePassed) return;
    setDispatching(true);

    try {
      const res = await fetch("/api/contract-assistant/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contract_id: contractId,
          recipients: [
            { name: "Primary Signer", email: "signer@gobitsnbytes.org", role: "signer" },
            { name: "Signatory 2", email: "legal@gobitsnbytes.org", role: "signer" },
          ],
        }),
      });

      if (res.ok) {
        alert("Contract successfully dispatched to bnb-signatures! Signatories notified.");
        window.location.href = "/dashboard/contract-assistant";
      } else {
        const errData = await res.json();
        alert(`Dispatch error: ${errData.detail || "Failed to dispatch"}`);
      }
    } catch (e) {
      alert("Dispatch error");
    } finally {
      setDispatching(false);
    }
  };

  const highCount = findings.filter((f) => f.severity === "high").length;
  const medCount = findings.filter((f) => f.severity === "medium").length;
  const lowCount = findings.filter((f) => f.severity === "low").length;

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6 pb-24">
      {/* Header Banner */}
      <div className="bg-white border-2 border-[#120F0A] p-5 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <Link
            href="/dashboard/contract-assistant"
            className="inline-flex items-center gap-1 text-xs font-bold text-[#716F6C] hover:text-[#97192C] mb-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Pipeline
          </Link>
          <h1 className="text-xl font-black text-[#120F0A] font-sans">{contractTitle}</h1>
          <div className="text-xs text-[#716F6C] font-medium mt-0.5">
            Counterparty: <b>{counterparty}</b> • ID: <span className="font-mono text-[#97192C]">{contractId}</span>
          </div>
        </div>

        {/* Executive Summary Strip */}
        <div className="flex items-center gap-2 bg-[#FAF8F5] border-2 border-[#120F0A] p-2 rounded-xl text-xs font-bold shadow-[2px_2px_0px_0px_#120F0A]">
          <span className="px-2.5 py-1 bg-red-100 text-red-800 rounded-lg border border-red-300">
            {highCount} High
          </span>
          <span className="px-2.5 py-1 bg-amber-100 text-amber-800 rounded-lg border border-amber-300">
            {medCount} Medium
          </span>
          <span className="px-2.5 py-1 bg-gray-100 text-gray-800 rounded-lg border border-gray-300">
            {lowCount} Low
          </span>
        </div>
      </div>

      {/* Two-Pane Review Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Pane: Document View */}
        <div className="lg:col-span-6 bg-white border-2 border-[#120F0A] rounded-2xl p-5 shadow-[4px_4px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center justify-between border-b border-gray-200 pb-3">
            <span className="text-xs font-black uppercase text-[#120F0A] flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-[#97192C]" /> Document Contract Clauses
            </span>
            <span className="text-[10px] font-mono font-bold text-[#716F6C] bg-gray-100 px-2 py-0.5 rounded">
              {clauses.length || findings.length} Clauses / Highlights
            </span>
          </div>

          <div className="space-y-4 font-mono text-xs leading-relaxed max-h-[600px] overflow-y-auto pr-1">
            {findings.map((item) => (
              <div
                key={item.id}
                onClick={() => setActiveFindingId(item.id)}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
                  activeFindingId === item.id
                    ? "border-[#120F0A] bg-[#FEE9CF]/40 shadow-[3px_3px_0px_0px_#120F0A]"
                    : "border-gray-200 bg-gray-50 hover:border-gray-400"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2 font-sans">
                  <span className="font-bold text-[#97192C]">{item.ref} {item.heading}</span>
                  <span
                    className={`text-[9px] font-black uppercase px-2 py-0.5 rounded ${
                      item.severity === "high"
                        ? "bg-red-600 text-white"
                        : item.severity === "medium"
                        ? "bg-amber-500 text-white"
                        : "bg-gray-200 text-gray-800"
                    }`}
                  >
                    {item.severity}
                  </span>
                </div>
                <div className="text-[#120F0A] bg-white p-2.5 rounded-lg border border-gray-200">
                  "{item.text}"
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Pane: Findings List */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white border-2 border-[#120F0A] rounded-2xl p-5 shadow-[4px_4px_0px_0px_#120F0A] space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 pb-3">
              <span className="text-xs font-black uppercase text-[#120F0A]">Clause Risk Triage</span>
              <span className="text-[10px] text-[#716F6C] font-bold">
                {findings.filter((f) => f.status === "open").length} Open Actions
              </span>
            </div>

            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
              {findings.map((finding) => {
                const isActive = activeFindingId === finding.id;
                const isResolved = finding.status !== "open";

                return (
                  <div
                    key={finding.id}
                    className={`border-2 rounded-xl p-4 space-y-3 transition-all ${
                      isActive ? "border-[#120F0A] bg-[#FAF8F5] shadow-[3px_3px_0px_0px_#120F0A]" : "border-gray-200 bg-white"
                    } ${isResolved ? "opacity-60" : ""}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-black text-[#97192C]">{finding.ref}</span>
                      <div className="flex items-center gap-1.5">
                        {finding.source === "rule_engine" ? (
                          <span className="bg-blue-100 text-blue-900 border border-blue-300 text-[10px] font-bold px-2 py-0.5 rounded">
                            ⚡ OKF Rule
                          </span>
                        ) : (
                          <span className="bg-purple-100 text-purple-900 border border-purple-300 text-[10px] font-bold px-2 py-0.5 rounded">
                            ✨ AI Pass
                          </span>
                        )}
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                            finding.severity === "high"
                              ? "bg-red-100 text-red-800"
                              : finding.severity === "medium"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {finding.severity}
                        </span>
                      </div>
                    </div>

                    <div className="text-xs font-bold text-[#120F0A]">{finding.heading}</div>
                    <p className="text-xs text-[#413F3B] font-medium leading-relaxed">{finding.plain_english}</p>

                    {/* Action Row */}
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#D0CFCE]">
                      {finding.tier === 1 ? (
                        <button
                          type="button"
                          disabled={isResolved}
                          onClick={() => handleResolveFinding(finding.id, "resolve")}
                          className="px-3 py-1.5 bg-[#97192C] text-white text-[11px] font-bold rounded-lg shadow-[1.5px_1.5px_0px_0px_#120F0A] hover:translate-y-[-1px] disabled:opacity-40"
                        >
                          Apply Standard Clause (Tier 1)
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={isResolved}
                          onClick={() => handleOpenRedlineModal(finding)}
                          className="px-3 py-1.5 bg-[#FC920D] text-[#120F0A] text-[11px] font-black rounded-lg border border-[#120F0A] shadow-[1.5px_1.5px_0px_0px_#120F0A] hover:translate-y-[-1px] disabled:opacity-40"
                        >
                          View Suggested Redline (Tier 2)
                        </button>
                      )}

                      <button
                        type="button"
                        disabled={isResolved}
                        onClick={() => handleResolveFinding(finding.id, "dismiss")}
                        className="px-2.5 py-1.5 bg-gray-100 text-gray-700 text-[11px] font-bold rounded-lg border border-gray-300 hover:bg-gray-200 disabled:opacity-40"
                      >
                        Dismiss
                      </button>

                      <button
                        type="button"
                        onClick={() => setChatOpenFindingId(chatOpenFindingId === finding.id ? null : finding.id)}
                        className="px-2.5 py-1.5 bg-white text-[#97192C] text-[11px] font-bold rounded-lg border border-[#120F0A] hover:bg-gray-50 flex items-center gap-1 ml-auto"
                      >
                        <MessageSquare className="w-3.5 h-3.5" /> Ask
                      </button>
                    </div>

                    {/* Inline Clause Chat */}
                    {chatOpenFindingId === finding.id && (
                      <div className="mt-3 p-3 bg-gray-50 border border-gray-300 rounded-xl space-y-2 font-sans">
                        <div className="text-[10px] font-bold text-[#716F6C] uppercase">Clause Inquiry Assistant</div>
                        <div className="space-y-1.5 max-h-32 overflow-y-auto">
                          {(clauseQuestions[finding.id] || []).map((q, qidx) => (
                            <div
                              key={qidx}
                              className={`p-2 rounded-lg text-xs font-medium ${
                                q.sender === "user" ? "bg-[#FEE9CF] text-[#120F0A] ml-4 text-right" : "bg-white border border-gray-200 text-[#120F0A] mr-4"
                              }`}
                            >
                              {q.text}
                            </div>
                          ))}
                        </div>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            placeholder="Ask why this was flagged..."
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleSendChatQuestion(finding.id)}
                            className="flex-1 px-3 py-1.5 bg-white border border-[#120F0A] rounded-lg text-xs font-bold"
                          />
                          <button
                            type="button"
                            onClick={() => handleSendChatQuestion(finding.id)}
                            className="px-3 py-1.5 bg-[#97192C] text-white text-xs font-bold rounded-lg"
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Redline Diff Modal */}
      {activeModalRedline && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-2xl w-full space-y-4">
            <div className="flex items-center justify-between border-b pb-3 border-gray-200">
              <h3 className="text-base font-black text-[#120F0A]">
                Tier-2 AI Suggested Redline Diff ({activeModalRedline.ref})
              </h3>
              <button
                type="button"
                onClick={() => setActiveModalRedline(null)}
                className="text-gray-500 hover:text-black font-bold text-sm"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold uppercase text-red-700 block mb-1">Original Clause</label>
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs font-mono text-red-950 leading-relaxed">
                  {activeModalRedline.text}
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold uppercase text-emerald-700 block mb-1">Suggested Redline Revision</label>
                <textarea
                  rows={5}
                  value={editedRewrite}
                  onChange={(e) => setEditedRewrite(e.target.value)}
                  className="w-full p-3 bg-emerald-50 border border-emerald-300 rounded-xl text-xs font-mono text-emerald-950 font-bold focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>
            </div>

            <div className="p-3 bg-gray-50 border rounded-xl text-xs text-[#716F6C] font-medium">
              <b>AI Reasoning &amp; Policy Citation:</b> {activeModalRedline.rationale}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setActiveModalRedline(null)}
                className="px-4 py-2 border-2 border-[#120F0A] rounded-xl text-xs font-bold text-[#120F0A] bg-white hover:bg-gray-100"
              >
                Reject Redline
              </button>
              <button
                type="button"
                onClick={handleAcceptRedline}
                className="px-5 py-2 bg-[#97192C] text-white text-xs font-bold border-2 border-[#120F0A] rounded-xl shadow-[2px_2px_0px_0px_#120F0A]"
              >
                Accept &amp; Apply Redline
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sticky Bottom Dispatch Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-[#120F0A] p-4 shadow-[0px_-4px_10px_rgba(0,0,0,0.1)] z-40">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="text-xs font-black text-[#120F0A] flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#97192C]" /> Dispatch Gate Validation Status
            </div>
            <div className="text-[11px] text-[#716F6C] font-medium">
              {isDispatchGatePassed ? (
                <span className="text-emerald-700 font-bold">
                  ✓ All high-severity findings resolved or dismissed. Ready to dispatch.
                </span>
              ) : (
                <span className="text-red-700 font-bold">
                  ⚠️ {highSeverityOpenCount} High-Severity Finding(s) must be resolved or explicitly dismissed before outbound send.
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            disabled={!isDispatchGatePassed || dispatching}
            onClick={handleDispatchToSignatures}
            className="w-full sm:w-auto px-6 py-3 bg-[#97192C] text-white text-xs font-black border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-1px] disabled:opacity-40 transition-all flex items-center justify-center gap-2"
          >
            {dispatching ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 text-[#FC920D]" />}
            Dispatch for Signature (bnb-signatures)
          </button>
        </div>
      </div>
    </div>
  );
}
