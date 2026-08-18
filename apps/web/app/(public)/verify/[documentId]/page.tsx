"use client";

import React, { useState, useEffect, use } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  FileText,
  Clock,
  AlertTriangle,
  ArrowLeft,
  XCircle,
  Download,
  Scale,
  Users,
  Lock,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";

interface VerifyPageProps {
  params: Promise<{ documentId: string }>;
}

export default function DocumentVerificationPage({ params }: VerifyPageProps) {
  const { documentId } = use(params);

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Compliance check report state
  const [complianceReport, setComplianceReport] = useState<any>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [showCompliance, setShowCompliance] = useState(false);

  useEffect(() => {
    fetchVerification();
  }, [documentId]);

  const fetchVerification = async () => {
    try {
      const res = await fetch(`/api/signatures/verify/${documentId}`);
      if (!res.ok) {
        setError("Document checksum or verification record not found in the official ledger.");
        return;
      }
      const certData = await res.json();
      setData(certData);
      // Fetch compliance report
      fetchCompliance(certData.document_id || documentId);
    } catch (e) {
      setError("Error verifying contract authenticity");
    } finally {
      setLoading(false);
    }
  };

  const fetchCompliance = async (id: string) => {
    setComplianceLoading(true);
    try {
      const res = await fetch(`/api/signatures/requests/${id}/compliance-check`);
      if (res.ok) {
        const comp = await res.json();
        setComplianceReport(comp);
      }
    } catch {
      // Compliance check is optional enrichment
    } finally {
      setComplianceLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex flex-col items-center justify-center p-6 space-y-3">
        <ShieldCheck className="w-10 h-10 text-[#97192C] animate-pulse" />
        <div className="text-xs font-bold text-[#716F6C]">
          Verifying cryptographic signature checksum and audit integrity...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-4">
          <AlertTriangle className="w-12 h-12 mx-auto text-[#97192C]" />
          <h1 className="text-lg font-black text-[#120F0A]">Verification Record Not Found</h1>
          <p className="text-xs text-[#716F6C] font-medium leading-relaxed">{error}</p>
          <div className="pt-2">
            <Link
              href="/verify"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A]"
            >
              <ArrowLeft className="w-4 h-4" /> Try another Checksum or File
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isVoided = data.status === "voided";
  const isCompleted = data.status === "completed";
  const isPending = !isVoided && !isCompleted;

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#120F0A] p-4 sm:p-8 max-w-5xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="bg-[#3C0A12] text-white border-2 border-[#120F0A] p-6 sm:p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-[#FC920D]" />
            <h1 className="text-xl font-black font-heading">Cryptographic Audit Certificate</h1>
          </div>
          <p className="text-xs text-[#FED39E] mt-1 font-medium">
            GOBITSNBYTES FOUNDATION Legal Operations &amp; Verification Portal
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/verify"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white text-[#120F0A] font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-1px] transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Lookup
          </Link>
          <Link
            href="/dashboard/signatures"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#FC920D] text-[#120F0A] font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-1px] transition-all"
          >
            Dashboard
          </Link>
        </div>
      </div>

      {/* Main Status Hero Card */}
      <div
        className={`border-2 border-[#120F0A] p-6 sm:p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-6 ${
          isVoided
            ? "bg-red-50 border-red-800"
            : isCompleted
            ? "bg-white"
            : "bg-[#FFFBF5]"
        }`}
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            {isVoided ? (
              <XCircle className="w-10 h-10 text-red-700 shrink-0 mt-0.5" />
            ) : isCompleted ? (
              <CheckCircle2 className="w-10 h-10 text-green-700 shrink-0 mt-0.5" />
            ) : (
              <Clock className="w-10 h-10 text-[#FC920D] shrink-0 mt-0.5" />
            )}

            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`text-[11px] font-black uppercase px-2.5 py-1 rounded-md border-2 border-[#120F0A] ${
                    isVoided
                      ? "bg-red-600 text-white"
                      : isCompleted
                      ? "bg-green-600 text-white"
                      : "bg-[#FC920D] text-[#120F0A]"
                  }`}
                >
                  {isVoided ? "OFFICIALLY QUASHED & VOIDED" : isCompleted ? "CRYPTOGRAPHICALLY SEALED & VALID" : "OUT FOR SIGNATURE"}
                </span>

                {complianceReport && (
                  <span className="text-[11px] font-bold bg-[#FAF8F5] text-[#120F0A] px-2.5 py-1 rounded-md border border-[#120F0A]">
                    ⚖️ Statutory Score: {complianceReport.compliance_score}%
                  </span>
                )}
              </div>

              <h2 className="text-xl font-black text-[#120F0A] mt-2 font-heading">{data.title}</h2>
              <div className="text-xs text-[#716F6C] font-mono mt-0.5">
                Document ID: <b>{data.document_id}</b>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isVoided ? (
              <a
                href={`/api/signatures/requests/${data.document_id}/export-void`}
                download
                className="px-4 py-2.5 bg-red-700 hover:bg-red-800 text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] flex items-center gap-1.5 transition-all"
              >
                <Download className="w-4 h-4" /> Download Revocation Certificate
              </a>
            ) : isCompleted ? (
              <a
                href={`/api/signatures/requests/${data.document_id}/download`}
                target="_blank"
                rel="noreferrer"
                className="px-4 py-2.5 bg-green-700 hover:bg-green-800 text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] flex items-center gap-1.5 transition-all"
              >
                <Download className="w-4 h-4" /> Download Executed PDF
              </a>
            ) : null}
          </div>
        </div>

        {/* Void notice if voided */}
        {isVoided && (
          <div className="bg-red-100/70 border-2 border-red-800 p-4 rounded-xl text-xs text-red-950 font-medium space-y-1.5">
            <div className="font-bold flex items-center gap-1.5 text-red-900">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              STATUTORY REVOCATION &amp; CANCELLATION NOTICE
            </div>
            <p className="leading-relaxed">
              This contract agreement has been officially quashed and voided by GOBITSNBYTES FOUNDATION. All electronic signing links, tokenized access portals, and legal enforceability have been permanently terminated.
            </p>
          </div>
        )}

        {/* Checksum and Signatory Summary Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t-2 border-[#120F0A] text-xs font-medium">
          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-3.5 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
            <span className="text-[#716F6C] font-bold block text-[10px] uppercase">Signatory Progress</span>
            <div className="text-base font-black text-[#120F0A] mt-0.5">
              {data.completed_signatories} of {data.total_signatories} Completed
            </div>
          </div>

          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-3.5 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
            <span className="text-[#716F6C] font-bold block text-[10px] uppercase">Creation Timestamp</span>
            <div className="text-xs font-mono font-bold text-[#120F0A] mt-1">
              {data.created_at ? new Date(data.created_at).toUTCString() : "—"}
            </div>
          </div>

          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-3.5 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
            <span className="text-[#716F6C] font-bold block text-[10px] uppercase">Completion Timestamp</span>
            <div className="text-xs font-mono font-bold text-[#120F0A] mt-1">
              {data.completed_at ? new Date(data.completed_at).toUTCString() : "Pending Execution"}
            </div>
          </div>

          <div className="md:col-span-3 bg-[#FAF8F5] border-2 border-[#120F0A] p-4 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
            <div className="flex items-center justify-between">
              <span className="text-[#716F6C] font-bold text-[10px] uppercase">
                Cryptographic SHA-256 Checksum Digest
              </span>
              <span className="text-[10px] text-green-800 font-bold bg-green-100 px-2 py-0.5 rounded border border-green-700">
                🔒 Tamper-Evident
              </span>
            </div>
            <div className="text-xs font-mono font-bold text-[#3C0A12] bg-white border border-[#120F0A] p-2.5 rounded-lg mt-2 break-all select-all">
              {data.document_hash || "Computing SHA-256 Hash..."}
            </div>
          </div>
        </div>
      </div>

      {/* Signatories Roster (if present) */}
      {data.recipients && data.recipients.length > 0 && (
        <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center gap-2 text-[#97192C]">
            <Users className="w-5 h-5" />
            <h2 className="text-sm font-black uppercase tracking-wider text-[#120F0A]">
              Designated Signatories Roster
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {data.recipients.map((r: any, idx: number) => (
              <div
                key={idx}
                className="bg-[#FAF8F5] border-2 border-[#120F0A] p-3.5 rounded-xl text-xs space-y-1 shadow-[2px_2px_0px_0px_#120F0A]"
              >
                <div className="flex items-center justify-between font-bold">
                  <span className="text-[#120F0A]">{r.name}</span>
                  <span
                    className={`uppercase text-[10px] px-2 py-0.5 rounded border ${
                      r.status === "signed"
                        ? "bg-green-100 text-green-900 border-green-800 font-bold"
                        : r.status === "declined" || isVoided
                        ? "bg-red-100 text-red-900 border-red-800 font-bold"
                        : "bg-amber-100 text-amber-900 border-amber-800 font-bold"
                    }`}
                  >
                    {isVoided && r.status !== "signed" ? "REVOKED" : r.status}
                  </span>
                </div>
                <div className="text-[11px] text-[#716F6C] font-mono">{r.email}</div>
                {r.signed_at && (
                  <div className="text-[10px] text-green-800 font-medium">
                    Signed: {new Date(r.signed_at).toUTCString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Statutory Legal Compliance Report (Interactive Accordion) */}
      {complianceReport && (
        <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center justify-between cursor-pointer" onClick={() => setShowCompliance(!showCompliance)}>
            <div className="flex items-center gap-2 text-[#97192C]">
              <Scale className="w-5 h-5" />
              <div>
                <h2 className="text-sm font-black uppercase tracking-wider text-[#120F0A]">
                  Statutory Legal &amp; Regulatory Compliance Checks
                </h2>
                <p className="text-[11px] text-[#716F6C] font-medium">
                  Audited under Indian &amp; International Electronic Execution Standards
                </p>
              </div>
            </div>
            <button className="px-3 py-1.5 bg-[#FAF8F5] border-2 border-[#120F0A] rounded-xl text-xs font-bold shadow-[2px_2px_0px_0px_#120F0A]">
              {showCompliance ? "Hide Details" : "Inspect 6 Standards"}
            </button>
          </div>

          {showCompliance && (
            <div className="pt-3 border-t-2 border-[#120F0A] space-y-3">
              {complianceReport.checks.map((c: any, i: number) => (
                <div
                  key={i}
                  className="bg-[#FAF8F5] border-2 border-[#120F0A] p-3.5 rounded-xl space-y-1 shadow-[2px_2px_0px_0px_#120F0A] text-xs"
                >
                  <div className="flex items-center justify-between font-bold">
                    <span className="text-[#120F0A] font-black">{c.title}</span>
                    <span
                      className={`text-[10px] uppercase font-black px-2 py-0.5 rounded border ${
                        c.passed
                          ? "bg-green-100 text-green-900 border-green-800"
                          : "bg-amber-100 text-amber-900 border-amber-800"
                      }`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <div className="text-[10px] text-[#97192C] font-bold">{c.statutory_reference}</div>
                  <div className="text-[#413F3B] text-[11px] leading-relaxed mt-1">{c.details}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Chronological Audit Log */}
      {data.audit_trail && data.audit_trail.length > 0 && (
        <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
          <div className="flex items-center gap-2 text-[#97192C]">
            <Clock className="w-5 h-5" />
            <h2 className="text-sm font-black uppercase tracking-wider text-[#120F0A]">
              Section 65B Chronological Audit Log
            </h2>
          </div>

          <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-[#D0CFCE]">
            {data.audit_trail.map((log: any, i: number) => (
              <div key={i} className="flex items-start gap-4 relative z-10 pl-1">
                <div className="w-6 h-6 rounded-full bg-[#FC920D] border-2 border-[#120F0A] flex items-center justify-center text-[10px] font-black text-[#120F0A]">
                  {i + 1}
                </div>
                <div className="flex-1 bg-[#FAF8F5] border-2 border-[#120F0A] p-3 rounded-xl shadow-[2px_2px_0px_0px_#120F0A] text-xs">
                  <div className="flex items-center justify-between font-bold text-[#120F0A]">
                    <span className="uppercase text-[#97192C] font-black">{log.action}</span>
                    <span className="text-[10px] text-[#716F6C] font-mono">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="mt-1 text-[#413F3B] font-medium leading-relaxed">{log.details}</div>
                  {log.ip_address && (
                    <div className="mt-1 text-[10px] text-[#716F6C] font-mono">IP: {log.ip_address}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
