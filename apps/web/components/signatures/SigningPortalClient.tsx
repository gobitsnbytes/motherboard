"use client";

import React, { useState, useEffect } from "react";
import { PenTool, CheckCircle2, ShieldCheck, Lock, AlertCircle, FileText } from "lucide-react";
import { SignatureCanvas } from "./SignatureCanvas";

interface SigningPortalClientProps {
  token: string;
}

export function SigningPortalClient({ token }: SigningPortalClientProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);

  const [passcode, setPasscode] = useState("");
  const [unlocked, setUnlocked] = useState(false);

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [activeSigFieldId, setActiveSigFieldId] = useState<string | null>(null);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [completed, setCompleted] = useState(false);

  const [statusDetails, setStatusDetails] = useState<any>(null);

  useEffect(() => {
    fetchPortalData();
  }, [token]);

  const fetchStatusDetails = async () => {
    try {
      const res = await fetch(`/api/signatures/sign/${token}/status`);
      if (res.ok) {
        const json = await res.json();
        setStatusDetails(json);
      }
    } catch (e) {
      console.error("Failed to fetch status details", e);
    }
  };

  useEffect(() => {
    if (completed) {
      fetchStatusDetails();
    }
  }, [completed]);

  const fetchPortalData = async () => {
    try {
      const res = await fetch(`/api/signatures/sign/${token}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Failed to load contract");
        return;
      }
      const portalData = await res.json();
      setData(portalData);

      // Pre-fill fullname and date defaults
      const defaults: Record<string, string> = {};
      const todayStr = new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      portalData.fields?.forEach((f: any) => {
        if (f.type === "fullname") {
          defaults[f.id] = portalData.recipient.name;
        } else if (f.type === "date") {
          defaults[f.id] = todayStr;
        }
      });
      setFieldValues(defaults);

      if (!portalData.recipient.requires_passcode) {
        setUnlocked(true);
      }
    } catch (e) {
      setError("Network error loading contract signing portal");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyPasscode = (e: React.FormEvent) => {
    e.preventDefault();
    if (passcode.trim()) {
      setUnlocked(true);
    }
  };

  const handleSaveSignature = (sigDataUrl: string) => {
    if (activeSigFieldId) {
      setFieldValues((prev) => ({ ...prev, [activeSigFieldId]: sigDataUrl }));
      setActiveSigFieldId(null);
    }
  };

  const handleSubmitSignature = async () => {
    if (!agreedToTerms) return;

    setSubmitting(true);
    const submittedFields = Object.entries(fieldValues).map(([field_id, value]) => ({
      field_id,
      value,
    }));

    try {
      const res = await fetch(`/api/signatures/sign/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fields: submittedFields,
          passcode: passcode || undefined,
        }),
      });

      if (res.ok) {
        setCompleted(true);
      } else {
        const errJson = await res.json().catch(() => ({}));
        alert(errJson.detail || "Signature submission failed");
      }
    } catch (e) {
      alert("Error submitting signature");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6 text-xs font-black uppercase tracking-wider text-[#716F6C] font-heading">
        Loading digital contract signing portal...
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-4">
          <AlertCircle className="w-12 h-12 mx-auto text-[#97192C]" />
          <h1 className="text-lg font-black text-[#120F0A] font-heading">Unable to Load Contract</h1>
          <p className="text-xs text-[#716F6C] font-medium">{error}</p>
        </div>
      </div>
    );
  }

  if (completed) {
    const isFullyCompleted = statusDetails?.request_status === "completed";

    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-5">
          <div
            className={`w-16 h-16 rounded-2xl border-2 mx-auto flex items-center justify-center shadow-[2px_2px_0px_0px_#120F0A] ${
              isFullyCompleted ? "bg-[#EFECE6] border-green-800 text-green-800" : "bg-[#FEE9CF] border-[#FC920D] text-[#FC920D]"
            }`}
          >
            <CheckCircle2 className="w-10 h-10" />
          </div>

          <h1 className="text-xl font-black text-[#120F0A] font-heading">
            {isFullyCompleted ? "Contract Fully Executed & Sealed!" : "Signature Recorded Successfully!"}
          </h1>

          <p className="text-xs text-[#716F6C] font-medium leading-relaxed">
            Thank you, <b>{data.recipient.name}</b>. Your signature has been recorded with a cryptographic timestamp.
          </p>

          {isFullyCompleted ? (
            <div className="bg-green-50 border-2 border-green-800 p-3 rounded-xl text-left text-xs space-y-1 font-medium text-green-900">
              <div className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" /> Cryptographically Sealed Document
              </div>
              <div>All required signatories have signed. The contract envelope is finalized.</div>
              {statusDetails?.document_hash && (
                <div className="text-[10px] font-mono text-green-800 truncate mt-1">
                  SHA-256: {statusDetails.document_hash}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[#FEE9CF]/50 border-2 border-[#120F0A] p-4 rounded-xl text-left space-y-2">
              <div className="text-xs font-bold text-[#120F0A] flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-[#97192C]" /> Envelope Pending Remaining Signatures
              </div>
              <p className="text-[11px] text-[#413F3B]">
                The contract will move to <b>Completed &amp; Sealed</b> once all signatories have finished:
              </p>
              <div className="space-y-1.5 pt-1">
                {statusDetails?.recipients?.map((r: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-[#120F0A]">
                      {r.name} ({r.role})
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[9px] font-bold border ${
                        r.status === "signed"
                          ? "bg-green-100 text-green-800 border-green-800"
                          : "bg-amber-100 text-amber-900 border-amber-800"
                      }`}
                    >
                      {r.status === "signed" ? "Signed" : "Pending Signature"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-2 text-[10px] text-[#716F6C] font-mono border-t border-[#D0CFCE]">
            Audit Event Recorded · SHA-256 Checksum Executed
          </div>
        </div>
      </div>
    );
  }

  if (!unlocked) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <form
          onSubmit={handleVerifyPasscode}
          className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full space-y-4"
        >
          <div className="w-14 h-14 rounded-2xl bg-[#FEE9CF] border-2 border-[#120F0A] mx-auto flex items-center justify-center text-[#97192C] shadow-[2px_2px_0px_0px_#120F0A]">
            <Lock className="w-7 h-7" />
          </div>
          <h1 className="text-lg font-black text-center text-[#120F0A] font-heading">Passcode Protected Contract</h1>
          <p className="text-xs text-center text-[#716F6C] font-medium">
            Enter the access passcode provided by the contract sender to view and sign.
          </p>

          <input
            type="password"
            placeholder="Enter security passcode..."
            value={passcode}
            onChange={(e) => setPasscode(e.target.value)}
            className="w-full px-4 py-2.5 border-2 border-[#120F0A] rounded-xl text-xs font-bold bg-white text-[#120F0A] shadow-[2px_2px_0px_0px_#120F0A]"
          />
          <button
            type="submit"
            className="w-full py-2.5 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A]"
          >
            Unlock &amp; View Contract
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#120F0A] p-4 sm:p-8 space-y-6 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="bg-white border-2 border-[#120F0A] p-5 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#97192C]" />
            <h1 className="text-lg font-black font-heading">{data.title}</h1>
          </div>
          <p className="text-xs text-[#716F6C] mt-0.5 font-medium">
            Signing as <b>{data.recipient.name}</b> (&lt;{data.recipient.email}&gt;)
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-bold text-green-800 bg-green-50 border-2 border-green-800 px-3.5 py-1.5 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
          <ShieldCheck className="w-4 h-4" /> Cryptographic E-Sign SSL
        </div>
      </div>

      {/* Contract Document Canvas Pages */}
      <div className="space-y-6">
        {data.previews.map((imgUrl: string, idx: number) => {
          const pageNum = idx + 1;
          const pageFields = data.fields.filter((f: any) => f.page_number === pageNum);

          return (
            <div
              key={pageNum}
              className="bg-white border-2 border-[#120F0A] rounded-2xl overflow-hidden shadow-[6px_6px_0px_0px_#120F0A] relative"
            >
              <div className="bg-[#FAF8F5] border-b-2 border-[#120F0A] px-4 py-2 text-xs font-black text-[#716F6C] font-mono">
                Page {pageNum} of {data.previews.length}
              </div>
              <div className="relative">
                <img src={imgUrl} alt={`Page ${pageNum}`} className="w-full h-auto pointer-events-none select-none block" />

                {/* Assigned Fields Overlays */}
                {pageFields.map((f: any) => {
                  const val = fieldValues[f.id];
                  return (
                    <div
                      key={f.id}
                      style={{
                        left: `${f.pos_x}%`,
                        top: `${f.pos_y}%`,
                        width: `${f.width}%`,
                        height: `${f.height}%`,
                      }}
                      onClick={() => {
                        if (f.type === "signature") {
                          setActiveSigFieldId(f.id);
                        }
                      }}
                      className={`absolute border-2 rounded-xl p-1.5 flex items-center justify-center cursor-pointer transition-all ${
                        val
                          ? "border-green-700 bg-green-50/90 shadow-md"
                          : "border-[#97192C] bg-[#F4D9D1] shadow-lg animate-pulse"
                      }`}
                    >
                      {f.type === "signature" ? (
                        val ? (
                          <img src={val} alt="Signature" className="max-h-full max-w-full object-contain" />
                        ) : (
                          <span className="flex items-center gap-1.5 text-xs font-black text-[#97192C] font-heading">
                            <PenTool className="w-4 h-4" /> Click to Sign
                          </span>
                        )
                      ) : (
                        <input
                          type="text"
                          placeholder={`Enter ${f.type}`}
                          value={val || ""}
                          onChange={(e) => setFieldValues({ ...fieldValues, [f.id]: e.target.value })}
                          className="w-full h-full bg-transparent text-xs font-bold text-[#120F0A] px-1 focus:outline-none"
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Signature Canvas Overlay Modal */}
      {activeSigFieldId && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <SignatureCanvas onSave={handleSaveSignature} onCancel={() => setActiveSigFieldId(null)} />
        </div>
      )}

      {/* Consent Disclosure & Submit Action */}
      <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={agreedToTerms}
            onChange={(e) => setAgreedToTerms(e.target.checked)}
            className="mt-1 w-4 h-4 rounded border-2 border-[#120F0A] accent-[#97192C]"
          />
          <span className="text-xs text-[#413F3B] font-medium leading-relaxed">
            I agree to sign this document electronically. I understand that my electronic signature is legally binding
            under applicable electronic signature regulations, and that my IP address and timestamp will be recorded in the audit
            trail certificate.
          </span>
        </label>

        <button
          type="button"
          disabled={!agreedToTerms || submitting}
          onClick={handleSubmitSignature}
          className="w-full py-3 bg-[#97192C] text-white font-bold text-sm border-2 border-[#120F0A] rounded-xl shadow-[4px_4px_0px_0px_#120F0A] hover:translate-y-[-1px] transition-all disabled:opacity-40"
        >
          {submitting ? "Submitting Signature..." : "Complete & Finish Signing"}
        </button>
      </div>
    </div>
  );
}
