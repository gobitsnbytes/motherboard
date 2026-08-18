"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Search, Upload, FileText, CheckCircle2, AlertTriangle, XCircle, ArrowRight, Lock, Scale, Clock } from "lucide-react";
import Link from "next/link";

export default function PublicVerificationPortal() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // File upload verification state
  const [verifyingFile, setVerifyingFile] = useState(false);
  const [fileResult, setFileResult] = useState<any>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanId = identifier.trim();
    if (!cleanId) {
      setSearchError("Please enter a Document ID, Access Token, or 64-character SHA-256 hash.");
      return;
    }
    setSearchError(null);
    router.push(`/verify/${cleanId}`);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setVerifyingFile(true);
    setFileResult(null);
    setFileError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/signatures/verify/file", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const json = await res.json();
        setFileResult(json);
      } else {
        const errJson = await res.json().catch(() => ({}));
        setFileError(errJson.detail || "Failed to verify document authenticity.");
      }
    } catch (err) {
      setFileError("Network error attempting to verify file against the registry.");
    } finally {
      setVerifyingFile(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#120F0A] p-4 sm:p-8 max-w-5xl mx-auto space-y-8">
      {/* Top Banner */}
      <div className="bg-[#3C0A12] text-white border-2 border-[#120F0A] p-6 sm:p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-8 h-8 text-[#FC920D]" />
            <h1 className="text-2xl font-black font-heading">Cryptographic Contract Verification</h1>
          </div>
          <p className="text-xs text-[#FED39E] mt-1 font-medium max-w-xl leading-relaxed">
            Validate document authenticity, cryptographic SHA-256 seals, and chronological audit trails under Section 10A of the IT Act, 2000 and Section 65B of the Indian Evidence Act.
          </p>
        </div>
        <Link
          href="/dashboard/signatures"
          className="px-4 py-2.5 bg-white text-[#120F0A] font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-1px] transition-all whitespace-nowrap"
        >
          Open Dashboard
        </Link>
      </div>

      {/* 2-Column Action Grid: ID Lookup & File Integrity Check */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Method 1: ID / Checksum Search */}
        <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-[#97192C]">
              <Search className="w-5 h-5" />
              <h2 className="text-base font-black font-heading text-[#120F0A]">Search by ID or Checksum</h2>
            </div>
            <p className="text-xs text-[#716F6C] font-medium leading-relaxed">
              Enter the unique <b>Document ID</b>, <b>Signatory Access Token</b>, or <b>64-character SHA-256 Hash</b> found on the contract certificate.
            </p>

            {searchError && (
              <div className="bg-red-50 border-2 border-red-800 text-red-900 p-2.5 rounded-xl text-xs font-bold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{searchError}</span>
              </div>
            )}

            <form onSubmit={handleSearch} className="space-y-3 pt-2">
              <input
                type="text"
                placeholder="e.g. 5f8817c8-... or a3f48c9b2e..."
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="w-full px-3.5 py-2.5 border-2 border-[#120F0A] rounded-xl text-xs font-mono font-bold bg-white text-[#120F0A] shadow-[2px_2px_0px_0px_#120F0A]"
              />
              <button
                type="submit"
                className="w-full py-2.5 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:bg-[#791423] transition-all flex items-center justify-center gap-1.5"
              >
                <Search className="w-4 h-4" /> Verify Document Identifier
              </button>
            </form>
          </div>

          <div className="text-[11px] text-[#716F6C] font-medium pt-3 border-t border-[#D0CFCE]">
            💡 Tip: Signatory access links (e.g. <code>/sign/sig_tok_...</code>) can be verified directly.
          </div>
        </div>

        {/* Method 2: PDF File Upload & Tamper Integrity Check */}
        <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-[#FC920D]">
              <Upload className="w-5 h-5 text-[#97192C]" />
              <h2 className="text-base font-black font-heading text-[#120F0A]">Upload PDF to Validate Seal</h2>
            </div>
            <p className="text-xs text-[#716F6C] font-medium leading-relaxed">
              Upload any executed contract PDF. Our engine will calculate its cryptographic hash in real-time and verify against the ledger.
            </p>

            {fileError && (
              <div className="bg-red-50 border-2 border-red-800 text-red-900 p-2.5 rounded-xl text-xs font-bold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{fileError}</span>
              </div>
            )}

            <div className="pt-2">
              <label className="border-2 border-dashed border-[#120F0A] rounded-xl p-6 bg-[#FAF8F5] hover:bg-[#FEE9CF]/30 transition-all flex flex-col items-center justify-center gap-2 cursor-pointer text-center">
                <FileText className="w-8 h-8 text-[#97192C]" />
                <span className="text-xs font-bold text-[#120F0A]">
                  {verifyingFile ? "Calculating SHA-256 Digest..." : "Click or Drag & Drop PDF File"}
                </span>
                <span className="text-[10px] text-[#716F6C]">Supports finalized signed PDFs (.pdf)</span>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  disabled={verifyingFile}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          <div className="text-[11px] text-[#716F6C] font-medium pt-3 border-t border-[#D0CFCE]">
            🔒 Zero data retention on verification: Files are hashed in-memory to detect post-execution tampering.
          </div>
        </div>
      </div>

      {/* File Verification Result Card (if uploaded) */}
      {fileResult && (
        <div className={`border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4 ${
          fileResult.is_authentic
            ? fileResult.status === "voided"
              ? "bg-red-50 border-red-800"
              : "bg-white"
            : "bg-red-50 border-red-800"
        }`}>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-3 border-b-2 border-[#120F0A]">
            <div className="flex items-center gap-3">
              {fileResult.is_authentic ? (
                fileResult.status === "voided" ? (
                  <XCircle className="w-8 h-8 text-red-700 shrink-0" />
                ) : (
                  <CheckCircle2 className="w-8 h-8 text-green-700 shrink-0" />
                )
              ) : (
                <AlertTriangle className="w-8 h-8 text-red-700 shrink-0" />
              )}
              <div>
                <div className="text-base font-black text-[#120F0A]">
                  {fileResult.is_authentic
                    ? fileResult.status === "voided"
                      ? "REVOKED & VOIDED RECORD FOUND"
                      : "CRYPTOGRAPHICALLY AUTHENTIC & VALID"
                    : "UNREGISTERED OR TAMPERED DOCUMENT"}
                </div>
                <div className="text-xs text-[#716F6C] font-mono mt-0.5">
                  Computed SHA-256: {fileResult.computed_hash}
                </div>
              </div>
            </div>

            {fileResult.document_id && (
              <Link
                href={`/verify/${fileResult.document_id}`}
                className="px-4 py-2 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[2px_2px_0px_0px_#120F0A] hover:bg-[#791423] transition-all flex items-center gap-1.5"
              >
                View Full Audit Trail <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>

          <p className="text-xs font-medium text-[#413F3B] leading-relaxed">{fileResult.details}</p>

          {fileResult.is_authentic && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-xs font-medium">
              <div className="bg-[#FAF8F5] border border-[#120F0A] p-3 rounded-xl">
                <span className="text-[#716F6C] font-bold block text-[10px] uppercase">Title</span>
                <span className="font-bold text-[#120F0A]">{fileResult.title}</span>
              </div>
              <div className="bg-[#FAF8F5] border border-[#120F0A] p-3 rounded-xl">
                <span className="text-[#716F6C] font-bold block text-[10px] uppercase">Status</span>
                <span className={`font-bold uppercase ${fileResult.status === "voided" ? "text-red-700" : "text-green-700"}`}>
                  {fileResult.status}
                </span>
              </div>
              <div className="bg-[#FAF8F5] border border-[#120F0A] p-3 rounded-xl">
                <span className="text-[#716F6C] font-bold block text-[10px] uppercase">Signatories Completed</span>
                <span className="font-bold text-[#120F0A]">
                  {fileResult.completed_signatories} of {fileResult.total_signatories}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Statutory Legal Validity Framework */}
      <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
        <div className="flex items-center gap-2 text-[#97192C]">
          <Scale className="w-5 h-5" />
          <h2 className="text-sm font-black font-heading uppercase tracking-wider text-[#120F0A]">
            Statutory Legal Framework (India &amp; Global)
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-medium">
          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-4 rounded-xl space-y-1.5 shadow-[2px_2px_0px_0px_#120F0A]">
            <div className="font-bold text-[#120F0A] text-sm">📜 Section 10A IT Act 2000</div>
            <p className="text-[#716F6C] text-[11px] leading-relaxed">
              Electronic contracts and tokenized signatures are statutory valid agreements admissible in Indian legal proceedings.
            </p>
          </div>

          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-4 rounded-xl space-y-1.5 shadow-[2px_2px_0px_0px_#120F0A]">
            <div className="font-bold text-[#120F0A] text-sm">⚖️ Section 65B Evidence Act</div>
            <p className="text-[#716F6C] text-[11px] leading-relaxed">
              Cryptographic SHA-256 hashes, timestamps, and IP logs constitute primary tamper-evident evidence under BSA 2023.
            </p>
          </div>

          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-4 rounded-xl space-y-1.5 shadow-[2px_2px_0px_0px_#120F0A]">
            <div className="font-bold text-[#120F0A] text-sm">🛡️ Section 8 Foundation</div>
            <p className="text-[#716F6C] text-[11px] leading-relaxed">
              Governed under GOBITSNBYTES FOUNDATION non-profit charter and Board authority matrix.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
