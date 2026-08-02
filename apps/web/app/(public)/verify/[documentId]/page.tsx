"use client";

import React, { useState, useEffect, use } from "react";
import { ShieldCheck, CheckCircle2, FileText, Clock, AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface VerifyPageProps {
  params: Promise<{ documentId: string }>;
}

export default function DocumentVerificationPage({ params }: VerifyPageProps) {
  const { documentId } = use(params);

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchVerification();
  }, [documentId]);

  const fetchVerification = async () => {
    try {
      const res = await fetch(`/api/signatures/verify/${documentId}`);
      if (!res.ok) {
        setError("Document checksum or verification record not found");
        return;
      }
      const certData = await res.json();
      setData(certData);
    } catch (e) {
      setError("Error verifying contract authenticity");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6 text-xs font-bold text-[#716F6C]">
        Verifying cryptographic signature checksum...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-4">
          <AlertTriangle className="w-12 h-12 mx-auto text-[#97192C]" />
          <h1 className="text-lg font-black text-[#120F0A]">Verification Failed</h1>
          <p className="text-xs text-[#716F6C] font-medium">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#120F0A] p-4 sm:p-8 max-w-4xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="bg-[#3C0A12] text-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-[#FC920D]" />
            <h1 className="text-xl font-black">Cryptographic Verification Certificate</h1>
          </div>
          <p className="text-xs text-[#FED39E] mt-1 font-medium">
            bits&bytes™ Legal Audit Engine (`bnb-signatures`)
          </p>
        </div>
        <Link
          href="/dashboard/signatures"
          className="flex items-center gap-1.5 px-4 py-2 bg-white text-[#120F0A] font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A]"
        >
          <ArrowLeft className="w-4 h-4" /> Return to Dashboard
        </Link>
      </div>

      {/* Verification Summary Box */}
      <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="w-8 h-8 text-green-600" />
          <div>
            <div className="text-base font-black text-[#120F0A]">{data.title}</div>
            <div className="text-xs text-[#716F6C] font-mono">Document ID: {data.document_id}</div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t-2 border-[#120F0A] text-xs font-medium">
          <div>
            <span className="text-[#716F6C] font-bold">Status:</span>
            <div className="text-sm font-bold text-green-700 uppercase mt-0.5">{data.status}</div>
          </div>
          <div>
            <span className="text-[#716F6C] font-bold">Signatories Progress:</span>
            <div className="text-sm font-bold text-[#120F0A] mt-0.5">
              {data.completed_signatories} of {data.total_signatories} Completed
            </div>
          </div>
          <div className="md:col-span-2">
            <span className="text-[#716F6C] font-bold">SHA-256 Tamper-Evident Checksum:</span>
            <div className="text-xs font-mono font-bold text-[#3C0A12] bg-[#F8F7F5] border border-[#120F0A] p-2 rounded-lg mt-1 break-all select-all">
              {data.document_hash || "Computing Hash..."}
            </div>
          </div>
        </div>
      </div>

      {/* Audit Trail Timeline */}
      <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
        <h2 className="text-sm font-black text-[#120F0A] uppercase tracking-wider">Chronological Audit Log</h2>

        <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-[#D0CFCE]">
          {data.audit_trail.map((log: any, i: number) => (
            <div key={i} className="flex items-start gap-4 relative z-10 pl-1">
              <div className="w-6 h-6 rounded-full bg-[#FC920D] border-2 border-[#120F0A] flex items-center justify-center text-[10px] font-black text-[#120F0A]">
                {i + 1}
              </div>
              <div className="flex-1 bg-[#FAF8F5] border-2 border-[#120F0A] p-3 rounded-xl shadow-[2px_2px_0px_0px_#120F0A] text-xs">
                <div className="flex items-center justify-between font-bold text-[#120F0A]">
                  <span className="uppercase text-[#97192C]">{log.action}</span>
                  <span className="text-[10px] text-[#716F6C] font-mono">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="mt-1 text-[#413F3B] font-medium">{log.details}</div>
                {log.ip_address && (
                  <div className="mt-1 text-[10px] text-[#716F6C] font-mono">IP: {log.ip_address}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
