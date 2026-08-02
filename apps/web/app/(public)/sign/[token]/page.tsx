"use client";

import React, { useState, useEffect, use } from "react";
import { PenTool, CheckCircle2, ShieldCheck, Lock, AlertCircle, FileText } from "lucide-react";
import { SignatureCanvas } from "../../../../components/signatures/SignatureCanvas";

interface SigningPageProps {
  params: Promise<{ token: string }>;
}

export default function PublicSigningPage({ params }: SigningPageProps) {
  const { token } = use(params);

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

  useEffect(() => {
    fetchPortalData();
  }, [token]);

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
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6 text-xs font-bold text-[#716F6C]">
        Loading digital contract signing portal...
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-4">
          <AlertCircle className="w-12 h-12 mx-auto text-[#97192C]" />
          <h1 className="text-lg font-black text-[#120F0A]">Unable to Load Contract</h1>
          <p className="text-xs text-[#716F6C] font-medium">{error}</p>
        </div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-green-100 border-2 border-green-800 text-green-800 mx-auto flex items-center justify-center">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <h1 className="text-xl font-black text-[#120F0A]">Contract Signed Successfully!</h1>
          <p className="text-xs text-[#716F6C] font-medium">
            Thank you, {data.recipient.name}. Your signature has been recorded and cryptographically sealed.
          </p>
          <div className="pt-2 text-[10px] text-[#716F6C] font-mono">
            Audit Event Recorded · SHA-256 Checksum Executed
          </div>
        </div>
      </div>
    );
  }

  if (!unlocked) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <form onSubmit={handleVerifyPasscode} className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full space-y-4">
          <div className="w-12 h-12 rounded-xl bg-[#FEE9CF] border-2 border-[#120F0A] mx-auto flex items-center justify-center text-[#97192C]">
            <Lock className="w-6 h-6" />
          </div>
          <h1 className="text-lg font-black text-center text-[#120F0A]">Passcode Protected Contract</h1>
          <p className="text-xs text-center text-[#716F6C]">Enter the access passcode provided by the contract sender to view and sign.</p>

          <input
            type="password"
            placeholder="Enter security passcode..."
            value={passcode}
            onChange={(e) => setPasscode(e.target.value)}
            className="w-full px-3 py-2 border-2 border-[#120F0A] rounded-xl text-xs font-bold bg-white"
          />
          <button
            type="submit"
            className="w-full py-2.5 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A]"
          >
            Unlock & View Contract
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
            <h1 className="text-lg font-black">{data.title}</h1>
          </div>
          <p className="text-xs text-[#716F6C] mt-0.5">
            Signing as <b>{data.recipient.name}</b> (&lt;{data.recipient.email}&gt;)
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-bold text-green-800 bg-green-50 border border-green-700 px-3 py-1.5 rounded-lg">
          <ShieldCheck className="w-4 h-4" /> Cryptographic E-Sign SSL
        </div>
      </div>

      {/* Contract Document Canvas Pages */}
      <div className="space-y-6">
        {data.previews.map((imgUrl: string, idx: number) => {
          const pageNum = idx + 1;
          const pageFields = data.fields.filter((f: any) => f.page_number === pageNum);

          return (
            <div key={pageNum} className="bg-white border-2 border-[#120F0A] rounded-2xl overflow-hidden shadow-[6px_6px_0px_0px_#120F0A] relative">
              <div className="bg-[#FAF8F5] border-b border-[#120F0A] px-4 py-2 text-xs font-bold text-[#716F6C]">
                Page {pageNum} of {data.previews.length}
              </div>
              <div className="relative">
                <img src={imgUrl} alt={`Page ${pageNum}`} className="w-full h-auto pointer-events-none select-none" />

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
                      className={`absolute border-2 rounded p-1 flex items-center justify-center cursor-pointer transition-all ${
                        val
                          ? "border-green-600 bg-green-50/80"
                          : "border-[#97192C] bg-[#F4D9D1] animate-pulse"
                      }`}
                    >
                      {f.type === "signature" ? (
                        val ? (
                          <img src={val} alt="Signature" className="max-h-full max-w-full object-contain" />
                        ) : (
                          <span className="flex items-center gap-1 text-xs font-bold text-[#97192C]">
                            <PenTool className="w-3.5 h-3.5" /> Click to Sign
                          </span>
                        )
                      ) : (
                        <input
                          type="text"
                          placeholder={`Enter ${f.type}`}
                          value={val || ""}
                          onChange={(e) => setFieldValues({ ...fieldValues, [f.id]: e.target.value })}
                          className="w-full h-full bg-transparent text-xs font-bold px-1 focus:outline-none"
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
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <SignatureCanvas
            onSave={handleSaveSignature}
            onCancel={() => setActiveSigFieldId(null)}
          />
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
            under applicable electronic signature regulations, and that my IP address and timestamp will be recorded in the audit trail certificate.
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
