"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, FileText, CheckCircle2, Clock, ShieldCheck, Download, ExternalLink, Search } from "lucide-react";

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
    status: string;
    signed_at?: string;
  }>;
}

export default function SignaturesDashboardPage() {
  const [requests, setRequests] = useState<SignatureRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"all" | "pending" | "completed">("all");
  const [searchQuery, setSearchQuery] = useState("");

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
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#3C0A12] text-white p-6 rounded-2xl border-2 border-[#120F0A] shadow-[6px_6px_0px_0px_#120F0A]">
        <div>
          <h1 className="text-2xl font-black tracking-tight font-sans">Digital Signatures & Contracts</h1>
          <p className="text-xs text-[#FED39E] mt-1 font-medium">
            Cryptographic, legally-binding contract workflow management (`bnb-signatures`).
          </p>
        </div>
        <Link
          href="/dashboard/signatures/builder"
          className="flex items-center gap-2 px-5 py-2.5 bg-[#FC920D] text-[#120F0A] font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-2px] transition-all"
        >
          <Plus className="w-4 h-4" /> New Signature Request
        </Link>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl shadow-[4px_4px_0px_0px_#120F0A] flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-[#FEE9CF] border border-[#120F0A] flex items-center justify-center text-[#97192C]">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-black text-[#120F0A]">{totalCount}</div>
            <div className="text-xs font-bold text-[#716F6C] uppercase tracking-wider">Total Contracts</div>
          </div>
        </div>

        <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl shadow-[4px_4px_0px_0px_#120F0A] flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-[#FED39E] border border-[#120F0A] flex items-center justify-center text-[#FC920D]">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-black text-[#120F0A]">{pendingCount}</div>
            <div className="text-xs font-bold text-[#716F6C] uppercase tracking-wider">Pending Outbound</div>
          </div>
        </div>

        <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl shadow-[4px_4px_0px_0px_#120F0A] flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-[#EFECE6] border border-[#120F0A] flex items-center justify-center text-green-700">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-black text-[#120F0A]">{completedCount}</div>
            <div className="text-xs font-bold text-[#716F6C] uppercase tracking-wider">Executed & Sealed</div>
          </div>
        </div>
      </div>

      {/* Search & Tabs Controls */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 bg-white border-2 border-[#120F0A] p-1 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "all" ? "bg-[#97192C] text-white" : "text-[#413F3B] hover:bg-gray-100"
            }`}
          >
            All Contracts ({totalCount})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("pending")}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "pending" ? "bg-[#97192C] text-white" : "text-[#413F3B] hover:bg-gray-100"
            }`}
          >
            Pending ({pendingCount})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("completed")}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "completed" ? "bg-[#97192C] text-white" : "text-[#413F3B] hover:bg-gray-100"
            }`}
          >
            Completed ({completedCount})
          </button>
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#716F6C]" />
          <input
            type="text"
            placeholder="Search contracts by title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-[#97192C] shadow-[2px_2px_0px_0px_#120F0A]"
          />
        </div>
      </div>

      {/* Contracts Table */}
      <div className="bg-white border-2 border-[#120F0A] rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs font-bold text-[#716F6C]">Loading signature contracts...</div>
        ) : filteredRequests.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <FileText className="w-10 h-10 mx-auto text-[#716F6C]" />
            <div className="text-sm font-bold text-[#120F0A]">No signature requests found</div>
            <p className="text-xs text-[#716F6C]">Get started by creating your first digital contract signature request.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAF8F5] border-b-2 border-[#120F0A] uppercase tracking-wider font-bold text-[#716F6C]">
                <tr>
                  <th className="p-4">Document Title</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Signatories</th>
                  <th className="p-4">Created Date</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#D0CFCE]">
                {filteredRequests.map((req) => (
                  <tr key={req.id} className="hover:bg-[#FEE9CF]/30 transition-colors font-medium">
                    <td className="p-4">
                      <div className="font-bold text-[#120F0A] text-sm">{req.title}</div>
                      {req.document_hash && (
                        <div className="text-[10px] text-[#716F6C] font-mono mt-0.5 truncate max-w-xs">
                          SHA256: {req.document_hash}
                        </div>
                      )}
                    </td>
                    <td className="p-4">
                      {req.status === "completed" ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-green-100 text-green-800 border border-green-800">
                          <CheckCircle2 className="w-3 h-3" /> Completed & Sealed
                        </span>
                      ) : req.status === "pending" ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-800">
                          <Clock className="w-3 h-3" /> Pending Signatures
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-gray-100 text-gray-800 border border-gray-600">
                          {req.status.toUpperCase()}
                        </span>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-1.5">
                        {req.recipients.map((r, i) => (
                          <div
                            key={i}
                            title={`${r.name} (${r.email}): ${r.status}`}
                            className={`w-6 h-6 rounded-full border border-[#120F0A] flex items-center justify-center text-[10px] font-bold ${
                              r.status === "signed" ? "bg-green-500 text-white" : "bg-gray-200 text-[#120F0A]"
                            }`}
                          >
                            {r.name.charAt(0).toUpperCase()}
                          </div>
                        ))}
                      </div>
                    </td>
                    <td className="p-4 text-[#716F6C]">
                      {new Date(req.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </td>
                    <td className="p-4 text-right space-x-2">
                      <a
                        href={`/api/signatures/requests/${req.id}/download`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border-2 border-[#120F0A] rounded-lg text-[11px] font-bold text-[#120F0A] hover:bg-gray-100 shadow-[1.5px_1.5px_0px_0px_#120F0A]"
                      >
                        <Download className="w-3 h-3" /> PDF
                      </a>
                      {req.document_hash && (
                        <Link
                          href={`/verify/${req.document_hash}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#97192C] text-white border-2 border-[#120F0A] rounded-lg text-[11px] font-bold shadow-[1.5px_1.5px_0px_0px_#120F0A]"
                        >
                          <ShieldCheck className="w-3 h-3" /> Verify
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
