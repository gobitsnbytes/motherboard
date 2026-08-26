"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, FileText, CheckCircle2, Clock, ShieldCheck, Download, ExternalLink, Search, Copy, Check, XCircle, Trash2, Mail, ScrollText, Stamp, Inbox, LayoutList } from "lucide-react";
import SignatureAuditModal from "components/signatures/SignatureAuditModal";
import LegalAgentPanel from "components/signatures/LegalAgentPanel";

interface SignatureRequestItem {
  id: string;
  title: string;
  status: "draft" | "pending" | "completed" | "voided" | "expired";
  document_hash?: string;
  created_at: string;
  completed_at?: string;
  recipients: Array<{
    id: string;
    name: string;
    email: string;
    role?: string;
    status: string;
    access_token: string;
    signed_at?: string;
  }>;
}

export default function SignaturesDashboardPage() {
  const [requests, setRequests] = useState<SignatureRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"all" | "pending" | "completed">("all");
  const [view, setView] = useState<"contracts" | "agent">("contracts");
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [auditRequestId, setAuditRequestId] = useState<string | null>(null);
  const [sealingId, setSealingId] = useState<string | null>(null);

  const orgSignerPending = (req: SignatureRequestItem) =>
    req.status === "pending" &&
    req.recipients.some((r) => r.role === "org_signer" && r.status !== "signed");

  const handleCountersign = async (id: string) => {
    setActionError(null);
    if (!confirm("Execute the organizational counter-signature as legal@gobitsnbytes.org? This binds GOBITSNBYTES FOUNDATION under your delegated authority and is recorded in the audit log.")) return;
    setSealingId(id);
    try {
      const res = await fetch(`/api/signatures/requests/${id}/countersign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = typeof data.detail === "string" ? data.detail : "Counter-signature failed.";
        setActionError(detail);
      } else {
        fetchRequests();
      }
    } catch {
      setActionError("Network error during counter-signature.");
    } finally {
      setSealingId(null);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const fetchRequests = async () => {
    try {
      const res = await fetch("/api/signatures/requests");
      if (res.ok) {
        const data = await res.json();
        setRequests(data);
      }
    } catch (e) {
      console.error("Failed to fetch signature requests", e);
    } finally {
      setLoading(false);
    }
  };

  const [resendingId, setResendingId] = useState<string | null>(null);

  const handleResend = async (requestId: string, recipientId: string) => {
    setResendingId(recipientId);
    try {
      const res = await fetch(`/api/signatures/requests/${requestId}/recipients/${recipientId}/resend`, {
        method: "POST",
      });
      if (res.ok) {
        alert("Signature invitation email resent successfully!");
      } else {
        alert("Failed to resend signature invitation.");
      }
    } catch (e) {
      console.error(e);
      alert("Error resending signature email.");
    } finally {
      setResendingId(null);
    }
  };

  const handleCopyLink = (accessToken: string) => {
    const fullUrl = `${window.location.origin}/sign/${accessToken}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedToken(accessToken);
    setTimeout(() => setCopiedToken(null), 2500);
  };

  const [actionError, setActionError] = useState<string | null>(null);

  const handleVoid = async (id: string) => {
    setActionError(null);
    if (!confirm("Are you sure you want to quash and void this agreement? Active signature links will be revoked.")) return;
    try {
      let res = await fetch(`/api/contract-assistant/contracts/${id}/void`, { method: "POST" });
      if (!res.ok) {
        res = await fetch(`/api/signatures/requests/${id}/void`, { method: "POST" });
      }
      if (res.ok) {
        fetchRequests();
      } else {
        const data = await res.json().catch(() => ({}));
        setActionError(data.detail || "Failed to void agreement. Please verify request status.");
      }
    } catch (e) {
      setActionError("Network error attempting to void agreement.");
    }
  };

  const handleDelete = async (id: string) => {
    setActionError(null);
    if (!confirm("This will download an official CANCELLED & VOID certificate copy to your device and permanently purge all database records. Proceed?")) return;
    try {
      let exportRes = await fetch(`/api/contract-assistant/contracts/${id}/export-void`);
      if (!exportRes.ok) {
        exportRes = await fetch(`/api/signatures/requests/${id}/export-void`);
      }
      if (exportRes.ok) {
        const blob = await exportRes.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `VOIDED_AGREEMENT_${id.substring(0, 8)}.txt`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }

      let deleteRes = await fetch(`/api/contract-assistant/contracts/${id}`, { method: "DELETE" });
      if (!deleteRes.ok) {
        deleteRes = await fetch(`/api/signatures/requests/${id}`, { method: "DELETE" });
      }
      if (deleteRes.ok) {
        fetchRequests();
      } else {
        const data = await deleteRes.json().catch(() => ({}));
        setActionError(data.detail || "Failed to purge agreement from database.");
      }
    } catch (e) {
      setActionError("Network error attempting to purge agreement.");
    }
  };

  const filteredRequests = requests.filter((r) => {
    if (activeTab === "pending" && r.status !== "pending") return false;
    if (activeTab === "completed" && r.status !== "completed") return false;
    if (searchQuery.trim()) {
      return r.title.toLowerCase().includes(searchQuery.toLowerCase());
    }
    return true;
  });

  const totalCount = requests.length;
  const pendingCount = requests.filter((r) => r.status === "pending").length;
  const completedCount = requests.filter((r) => r.status === "completed").length;

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Action Error Banner */}
      {actionError && (
        <div className="p-3 bg-red-950/80 border-2 border-red-500 rounded-base text-red-200 text-xs font-mono font-bold flex items-center justify-between shadow-light">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-red-400 hover:text-white font-bold ml-2">✕</button>
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#141418] text-white p-5 rounded-base border-2 border-border shadow-dark">
        <div>
          <h1 className="text-2xl sm:text-3xl font-heading font-black tracking-tight uppercase">
            Digital Signatures &amp; Contracts
          </h1>
          <p className="text-xs sm:text-sm text-zinc-300 mt-1 font-base">
            Cryptographic, legally-binding contract workflow management (`bnb-signatures`).
          </p>
        </div>
        <Link
          href="/dashboard/signatures/builder"
          className="flex items-center gap-2 px-4 py-2.5 bg-orange text-black font-heading font-black text-xs uppercase tracking-wider border-2 border-black rounded-base shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
        >
          <Plus className="w-4 h-4" /> New Signature Request
        </Link>
      </div>

      {/* View Toggle: Contracts | Legal Agent Inbox */}
      <div className="flex w-fit items-center gap-2 rounded-base border-2 border-border bg-[#141418] p-1 shadow-light">
        <button
          type="button"
          onClick={() => setView("contracts")}
          className={`flex items-center gap-1.5 rounded-base px-4 py-1.5 text-xs font-mono font-bold uppercase transition-all ${
            view === "contracts" ? "bg-orange text-black border border-black shadow-light" : "text-zinc-300 hover:text-white"
          }`}
        >
          <LayoutList className="w-3.5 h-3.5" /> Contracts
        </button>
        <button
          type="button"
          onClick={() => setView("agent")}
          className={`flex items-center gap-1.5 rounded-base px-4 py-1.5 text-xs font-mono font-bold uppercase transition-all ${
            view === "agent" ? "bg-orange text-black border border-black shadow-light" : "text-zinc-300 hover:text-white"
          }`}
        >
          <Inbox className="w-3.5 h-3.5" /> Legal Agent Inbox
        </button>
      </div>

      {view === "agent" && <LegalAgentPanel />}

      {view === "contracts" && (
      <>
      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#141418] border-2 border-border p-4 rounded-base shadow-light flex items-center gap-4">
          <div className="w-10 h-10 rounded-base bg-main/20 border-2 border-border flex items-center justify-center text-orange">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-heading font-black text-white">{totalCount}</div>
            <div className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">Total Contracts</div>
          </div>
        </div>

        <div className="bg-[#141418] border-2 border-border p-4 rounded-base shadow-light flex items-center gap-4">
          <div className="w-10 h-10 rounded-base bg-amber-500/20 border-2 border-border flex items-center justify-center text-amber-400">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-heading font-black text-white">{pendingCount}</div>
            <div className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">Pending Outbound</div>
          </div>
        </div>

        <div className="bg-[#141418] border-2 border-border p-4 rounded-base shadow-light flex items-center gap-4">
          <div className="w-10 h-10 rounded-base bg-emerald-500/20 border-2 border-border flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-heading font-black text-white">{completedCount}</div>
            <div className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">Executed &amp; Sealed</div>
          </div>
        </div>
      </div>

      {/* Search & Tabs Controls */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 bg-[#141418] border-2 border-border p-1 rounded-base shadow-light">
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded-base text-xs font-mono font-bold uppercase transition-all ${
              activeTab === "all" ? "bg-orange text-black border border-black shadow-light" : "text-zinc-400 hover:text-white"
            }`}
          >
            All Contracts ({totalCount})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("pending")}
            className={`px-3 py-1.5 rounded-base text-xs font-mono font-bold uppercase transition-all ${
              activeTab === "pending" ? "bg-orange text-black border border-black shadow-light" : "text-zinc-400 hover:text-white"
            }`}
          >
            Pending ({pendingCount})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("completed")}
            className={`px-3 py-1.5 rounded-base text-xs font-mono font-bold uppercase transition-all ${
              activeTab === "completed" ? "bg-orange text-black border border-black shadow-light" : "text-zinc-400 hover:text-white"
            }`}
          >
            Completed ({completedCount})
          </button>
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search contracts by title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-black border-2 border-border rounded-base text-xs font-mono text-white focus:outline-none focus:border-orange shadow-light"
          />
        </div>
      </div>

      {/* Contracts Table */}
      <div className="bg-[#141418] border-2 border-border rounded-base shadow-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs font-mono font-bold text-zinc-400">Loading signature contracts...</div>
        ) : filteredRequests.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <FileText className="w-10 h-10 mx-auto text-zinc-600" />
            <div className="text-sm font-heading font-black uppercase tracking-wider text-white">No signature requests found</div>
            <p className="text-xs text-zinc-400 font-mono">Get started by creating your first digital contract signature request.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#121216] border-b-2 border-border uppercase tracking-wider font-mono font-bold text-zinc-400">
                <tr>
                  <th className="p-4">Document Title</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Signatories &amp; Links</th>
                  <th className="p-4">Created Date</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredRequests.map((req) => (
                  <tr key={req.id} className="hover:bg-[#181820] transition-colors font-medium">
                    <td className="p-4">
                      <div className="font-bold text-white text-sm">{req.title}</div>
                      {req.document_hash && (
                        <div className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate max-w-xs">
                          SHA256: {req.document_hash}
                        </div>
                      )}
                    </td>
                    <td className="p-4">
                      {req.status === "completed" ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-base text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                          <CheckCircle2 className="w-3 h-3" /> Completed &amp; Sealed
                        </span>
                      ) : req.status === "pending" ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-base text-[10px] font-mono font-bold bg-amber-950 text-amber-400 border border-amber-800">
                          <Clock className="w-3 h-3" /> Pending Signatures
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-base text-[10px] font-mono font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
                          {req.status.toUpperCase()}
                        </span>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="space-y-1.5">
                        {req.recipients.map((r) => {
                          const isCopied = copiedToken === r.access_token;
                          const isOrg = r.role === "org_signer";
                          return (
                            <div key={r.id} className="flex items-center gap-2 text-xs font-mono">
                              <span
                                className={`w-2.5 h-2.5 rounded-full border border-border shrink-0 ${
                                  r.status === "signed" ? "bg-emerald-400" : "bg-amber-400"
                                }`}
                                title={r.status}
                              />
                              <span className="font-bold text-zinc-200 truncate max-w-[120px]">{r.name}</span>
                              {isOrg && (
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-base border border-black bg-orange text-[9px] font-black uppercase text-black">
                                  <Stamp className="w-2.5 h-2.5" /> Org Seal {r.status === "signed" ? "✓" : "Pending"}
                                </span>
                              )}
                              {!isOrg && (
                              <button
                                type="button"
                                onClick={() => handleCopyLink(r.access_token)}
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-base border text-[10px] font-mono font-bold transition-all ${
                                  isCopied
                                    ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                                    : "bg-[#181820] text-zinc-300 border-border hover:bg-orange hover:text-black hover:border-black"
                                }`}
                                title="Copy direct signing link"
                              >
                              {isCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                                {isCopied ? "Copied Link!" : "Copy Link"}
                              </button>
                              )}
                              {r.status !== "signed" && !isOrg && (
                                <button
                                  type="button"
                                  onClick={() => handleResend(req.id, r.id)}
                                  disabled={resendingId === r.id}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-base border text-[10px] font-mono font-bold transition-all bg-[#181820] text-zinc-300 border-border hover:bg-main hover:text-white disabled:opacity-50"
                                  title="Resend signature email notification"
                                >
                                  <Mail className="w-3 h-3" />
                                  {resendingId === r.id ? "Sending..." : "Resend"}
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </td>
                    <td className="p-4 text-zinc-400 font-mono text-xs">
                      {new Date(req.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </td>
                    <td className="p-4 text-right space-x-1.5">
                      <button
                        type="button"
                        onClick={() => setAuditRequestId(req.id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#181820] border-2 border-border rounded-base text-[11px] font-mono font-bold text-zinc-200 hover:bg-white/10 shadow-light"
                        title="View signature audit trail"
                      >
                        <ScrollText className="w-3 h-3 text-orange" /> Audit
                      </button>
                      {orgSignerPending(req) && (
                        <button
                          type="button"
                          onClick={() => handleCountersign(req.id)}
                          disabled={sealingId === req.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-orange text-black border-2 border-black rounded-base text-[11px] font-mono font-bold shadow-light hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none disabled:opacity-50"
                          title="Execute legal@gobitsnbytes.org counter-signature (delegated authority)"
                        >
                          <Stamp className="w-3 h-3" />
                          {sealingId === req.id ? "Sealing…" : "Org Seal"}
                        </button>
                      )}
                      <a
                        href={`/api/signatures/requests/${req.id}/download`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#181820] border-2 border-border rounded-base text-[11px] font-mono font-bold text-zinc-200 hover:bg-white/10 shadow-light"
                      >
                        <Download className="w-3 h-3 text-zinc-400" /> PDF
                      </a>
                      <Link
                        href={`/verify/${req.document_hash || req.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-main text-white border-2 border-border rounded-base text-[11px] font-mono font-bold shadow-light hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none"
                      >
                        <ShieldCheck className="w-3 h-3" /> Verify
                      </Link>
                      {req.status !== "voided" && (
                        <button
                          type="button"
                          onClick={() => handleVoid(req.id)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-[#181820] hover:bg-red-950/80 text-zinc-300 border-2 border-border rounded-base text-[11px] font-mono font-bold shadow-light"
                          title="Void / Quash agreement"
                        >
                          <XCircle className="w-3 h-3 text-red-400" /> Void
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(req.id)}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-red-950 hover:bg-red-900 text-red-200 border-2 border-red-800 rounded-base text-[11px] font-mono font-bold shadow-light"
                        title="Download voided copy and permanently delete record"
                      >
                        <Trash2 className="w-3 h-3" /> Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </>
      )}
      <SignatureAuditModal
        requestId={auditRequestId}
        onClose={() => setAuditRequestId(null)}
      />
    </div>
  );
}
