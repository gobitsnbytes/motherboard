"use client";

import React, { useState, useEffect } from "react";
import { PenTool, CheckCircle2, ShieldCheck, Lock, AlertCircle, FileText, Mail, Scale, BookOpen, X, Info } from "lucide-react";
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
  const [showLegalModal, setShowLegalModal] = useState(false);

  // OTP Verification state
  const [confirmEmail, setConfirmEmail] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpSending, setOtpSending] = useState(false);
  const [otpVerifying, setOtpVerifying] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState(120); // 2 minutes in seconds

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [activeSigFieldId, setActiveSigFieldId] = useState<string | null>(null);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [completed, setCompleted] = useState(false);

  const [statusDetails, setStatusDetails] = useState<any>(null);

  useEffect(() => {
    fetchPortalData();
  }, [token]);

  useEffect(() => {
    if (!otpSent || timeLeft <= 0) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [otpSent, timeLeft]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

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

      if (!portalData.recipient.requires_passcode && !portalData.recipient.requires_otp) {
        setUnlocked(true);
      }
    } catch (e) {
      setError("Network error loading contract signing portal");
    } finally {
      setLoading(false);
    }
  };

  const handleRequestOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!confirmEmail.trim()) {
      setOtpError("Please enter your full email address to proceed");
      return;
    }
    setOtpSending(true);
    setOtpError(null);
    try {
      const res = await fetch(`/api/signatures/sign/${token}/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: confirmEmail.trim() }),
      });
      if (res.ok) {
        setOtpSent(true);
        setTimeLeft(120);
      } else {
        const errJson = await res.json().catch(() => ({}));
        setOtpError(errJson.detail || "Failed to send OTP email");
      }
    } catch (e) {
      setOtpError("Network error requesting OTP");
    } finally {
      setOtpSending(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpCode.trim()) return;
    if (timeLeft <= 0) {
      setOtpError("Verification code has expired. Please request a new code.");
      return;
    }
    setOtpVerifying(true);
    setOtpError(null);
    try {
      const res = await fetch(`/api/signatures/sign/${token}/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ otp: otpCode.trim() }),
      });
      if (res.ok) {
        setOtpVerified(true);
        if (!data?.recipient?.requires_passcode || passcode) {
          setUnlocked(true);
        }
      } else {
        const errJson = await res.json().catch(() => ({}));
        setOtpError(errJson.detail || "Invalid verification code");
      }
    } catch (e) {
      setOtpError("Network error verifying OTP");
    } finally {
      setOtpVerifying(false);
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

  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmitSignature = async () => {
    if (!agreedToTerms) return;

    setSubmitting(true);
    setSubmitError(null);
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
        setSubmitError(errJson.detail || "Signature submission failed. Please ensure all required fields are filled.");
      }
    } catch (e) {
      setSubmitError("Network error submitting signature. Please try again.");
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

  if (data?.status === "voided" || data?.recipient?.status === "declined" || data?.recipient?.status === "voided") {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-red-50 border-2 border-red-800 p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full text-center space-y-4">
          <AlertCircle className="w-12 h-12 mx-auto text-red-700" />
          <h1 className="text-xl font-black text-red-950 font-heading">Contract Agreement Revoked</h1>
          <p className="text-xs text-red-900 font-medium leading-relaxed">
            This contract agreement has been officially quashed and voided by the issuing authority. Signature collection and execution permissions for this document are terminated.
          </p>
          <div className="pt-2">
            <a
              href={`/api/signatures/requests/${data.id || data.recipient.request_id}/export-void`}
              download
              className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-red-700 hover:bg-red-800 text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A]"
            >
              Download Revocation Certificate
            </a>
          </div>
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

  if (data?.recipient?.requires_otp && !otpVerified) {
    const maskedEmail = data.recipient.masked_email || data.recipient.email;
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="bg-white border-2 border-[#120F0A] p-8 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] max-w-md w-full space-y-4 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[#FEE9CF] border-2 border-[#120F0A] mx-auto flex items-center justify-center text-[#97192C] shadow-[2px_2px_0px_0px_#120F0A]">
            <Mail className="w-7 h-7" />
          </div>
          <h1 className="text-lg font-black text-[#120F0A] font-heading">Signatory Identity Verification</h1>
          <p className="text-xs text-[#716F6C] font-medium leading-relaxed">
            To view and sign this contract, confirm your full email address matching:
            <br />
            <b className="text-[#97192C] font-mono text-sm tracking-wide block mt-1">{maskedEmail}</b>
          </p>

          {otpError && (
            <div className="bg-red-50 border-2 border-red-800 text-red-900 p-2.5 rounded-xl text-xs font-bold flex items-center gap-2 text-left">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{otpError}</span>
            </div>
          )}

          {!otpSent ? (
            <form onSubmit={handleRequestOtp} className="space-y-3 pt-1 text-left">
              <div>
                <label className="block text-[11px] font-bold text-[#120F0A] uppercase tracking-wider mb-1">
                  Enter Full Email Address
                </label>
                <input
                  type="email"
                  placeholder="e.g. signatory@organization.org"
                  value={confirmEmail}
                  onChange={(e) => setConfirmEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 border-2 border-[#120F0A] rounded-xl text-xs font-bold bg-white text-[#120F0A] shadow-[2px_2px_0px_0px_#120F0A]"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={otpSending || !confirmEmail.trim()}
                className="w-full py-2.5 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:bg-[#791423] transition-colors disabled:opacity-50 mt-2"
              >
                {otpSending ? "Verifying Email & Sending PIN..." : "Verify Email & Send 6-Digit PIN"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp} className="space-y-3 pt-1 text-left">
              <div className="bg-green-50 border-2 border-green-800 p-3 rounded-xl text-xs text-green-900 font-bold space-y-1">
                <div className="flex items-center justify-between">
                  <span>6-Digit PIN Sent to Email!</span>
                  <span className={`font-mono text-xs px-2 py-0.5 rounded border ${timeLeft > 0 ? "bg-green-200 border-green-800 text-green-900" : "bg-red-200 border-red-800 text-red-900"}`}>
                    {timeLeft > 0 ? formatTime(timeLeft) : "Expired"}
                  </span>
                </div>
                <div className="text-[11px] font-normal text-green-800">
                  {timeLeft > 0 ? "PIN is valid for 2 minutes. Enter code to proceed." : "Code expired. Please request a new PIN."}
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-[#120F0A] uppercase tracking-wider mb-1">
                  Enter 6-Digit Verification Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="------"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                  className="w-full px-4 py-3 border-2 border-[#120F0A] rounded-xl text-xl font-black tracking-[0.4em] text-center bg-white text-[#97192C] shadow-[2px_2px_0px_0px_#120F0A]"
                />
              </div>

              <button
                type="submit"
                disabled={otpVerifying || otpCode.length !== 6 || timeLeft <= 0}
                className="w-full py-2.5 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] hover:bg-[#791423] transition-colors disabled:opacity-50"
              >
                {otpVerifying ? "Verifying Code..." : "Verify Code & Unlock Document"}
              </button>

              <div className="flex items-center justify-between pt-2 text-[11px]">
                <button
                  type="button"
                  onClick={() => {
                    setOtpSent(false);
                    setOtpCode("");
                  }}
                  className="font-bold text-[#716F6C] hover:text-[#120F0A] underline"
                >
                  Change Email
                </button>
                <button
                  type="button"
                  onClick={(e) => handleRequestOtp(e)}
                  disabled={otpSending}
                  className="font-bold text-[#97192C] hover:underline disabled:opacity-50"
                >
                  {otpSending ? "Resending..." : "Resend PIN"}
                </button>
              </div>
            </form>
          )}
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
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowLegalModal(true)}
            className="flex items-center gap-1.5 text-xs font-bold text-[#97192C] bg-[#FEE9CF] hover:bg-[#FED39E] border-2 border-[#120F0A] px-3.5 py-1.5 rounded-xl shadow-[2px_2px_0px_0px_#120F0A] transition-all"
          >
            <Scale className="w-4 h-4" /> Legal Disclosures
          </button>
          <div className="flex items-center gap-1.5 text-xs font-bold text-green-800 bg-green-50 border-2 border-green-800 px-3.5 py-1.5 rounded-xl shadow-[2px_2px_0px_0px_#120F0A]">
            <ShieldCheck className="w-4 h-4" /> Cryptographic SSL
          </div>
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
                      className={`absolute border-2 rounded-lg flex items-center justify-center p-2 cursor-pointer transition-all ${
                        val
                          ? "bg-green-50/90 border-green-800 text-green-950 font-bold"
                          : "bg-[#FEE9CF]/80 border-[#97192C] text-[#97192C] font-bold hover:bg-[#FED39E] shadow-[2px_2px_0px_0px_#120F0A]"
                      }`}
                    >
                      {f.type === "signature" ? (
                        val ? (
                          <img src={val} alt="Signature" className="max-h-full max-w-full object-contain" />
                        ) : (
                          <div className="flex items-center gap-1.5 text-xs">
                            <PenTool className="w-4 h-4" /> Sign Here ({f.recipient_name || "Assigned"})
                          </div>
                        )
                      ) : (
                        <input
                          type={f.type === "date" ? "date" : "text"}
                          placeholder={f.label || f.type}
                          value={val || ""}
                          onChange={(e) => setFieldValues({ ...fieldValues, [f.id]: e.target.value })}
                          className="w-full h-full bg-transparent border-none focus:outline-none text-xs font-bold"
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
          <SignatureCanvas
            onSave={handleSaveSignature}
            onCancel={() => setActiveSigFieldId(null)}
            allowedSigType={data.recipient?.allowed_sig_type || "any"}
          />
        </div>
      )}

      {/* Full Legal & Statutory Disclosures Modal */}
      {showLegalModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-6 rounded-2xl shadow-[8px_8px_0px_0px_#120F0A] max-w-2xl w-full max-h-[85vh] overflow-y-auto space-y-4 text-left">
            <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-3">
              <div className="flex items-center gap-2 text-[#97192C]">
                <Scale className="w-6 h-6" />
                <h2 className="text-lg font-black font-heading text-[#120F0A]">
                  Statutory Legal Validity &amp; Disclosure
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowLegalModal(false)}
                className="p-1 rounded-lg border-2 border-[#120F0A] bg-white hover:bg-gray-100"
              >
                <X className="w-5 h-5 text-[#120F0A]" />
              </button>
            </div>

            <div className="space-y-4 text-xs text-[#413F3B] leading-relaxed">
              <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl space-y-2">
                <div className="font-bold text-sm text-[#120F0A] flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4 text-[#97192C]" /> 1. Operating Legal Entity &amp; Governance
                </div>
                <p>
                  This electronic contract infrastructure is operated under the legal authority of <b>GOBITSNBYTES FOUNDATION</b>, a Section 8 non-profit company registered under the Companies Act, 2013, based in Uttar Pradesh, India. The Foundation is legally governed by its Board of Directors. Operating publicly as <b>bits&amp;bytes™</b>.
                </p>
              </div>

              <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl space-y-2">
                <div className="font-bold text-sm text-[#120F0A] flex items-center gap-1.5">
                  <Scale className="w-4 h-4 text-[#97192C]" /> 2. Information Technology Act, 2000 (Section 10A)
                </div>
                <p>
                  In accordance with <b>Section 10A of the Indian Information Technology Act, 2000</b>:
                </p>
                <blockquote className="bg-[#FAF8F5] border-l-4 border-[#97192C] p-2.5 font-mono text-[11px] text-[#120F0A] italic">
                  "Where in a contract formation, communication of proposals, acceptance of proposals, revocation of proposals and acceptances, as the case may be, are expressed in electronic form or by means of an electronic record, such contract shall not be deemed to be unenforceable solely on the ground that such electronic form or means was used for that purpose."
                </blockquote>
              </div>

              <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl space-y-2">
                <div className="font-bold text-sm text-[#120F0A] flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-[#97192C]" /> 3. Primary Evidence Admissibility (Section 65B BSA / Evidence Act)
                </div>
                <p>
                  Every contract executed through <code>bnb-signatures</code> generates an immutable electronic record. The resulting audit certificate includes:
                </p>
                <ul className="list-disc list-inside space-y-1 font-medium pl-1 text-[11px]">
                  <li>SHA-256 Cryptographic Checksum of the original and signed PDF document</li>
                  <li>UTC &amp; IST Execution Timestamps registered at submission</li>
                  <li>Signatory IP Address &amp; User-Agent Browser Metadata</li>
                  <li>6-Digit Email OTP verification log (where enabled)</li>
                  <li>X.509 Digital Signature Certificate (Class 1 / 2 / 3 DSC) serial numbers (where attached)</li>
                </ul>
                <p className="text-[11px] text-[#716F6C]">
                  Under Section 65B of the Indian Evidence Act, 1872 (Bharatiya Sakshya Adhiniyam, 2023), these electronic audit logs constitute primary admissible evidence in Indian courts.
                </p>
              </div>

              <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl space-y-2">
                <div className="font-bold text-sm text-[#120F0A] flex items-center gap-1.5">
                  <Lock className="w-4 h-4 text-[#97192C]" /> 4. Data Protection &amp; Minor Safeguarding (DPDP Act 2023 &amp; POCSO)
                </div>
                <p>
                  All signatory identifiers, email addresses, and timestamps are processed strictly under the <b>Digital Personal Data Protection Act, 2023 (DPDP Act)</b> and the <b>Protection of Children from Sexual Offences Act, 2012 (POCSO)</b>. Personal data is never traded, sold, or shared with unauthorized third parties.
                </p>
              </div>

              <div className="bg-white border-2 border-[#120F0A] p-4 rounded-xl space-y-2">
                <div className="font-bold text-sm text-[#120F0A] flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-[#97192C]" /> 5. Cryptographic Tamper Evident Sealing
                </div>
                <p>
                  Once all signatories complete execution, the document envelope is sealed. Any post-execution modification to the file breaks the SHA-256 cryptographic digest, rendering unauthorized edits instantly detectable.
                </p>
              </div>
            </div>

            <div className="pt-3 border-t border-[#D0CFCE] flex justify-end">
              <button
                type="button"
                onClick={() => setShowLegalModal(false)}
                className="px-5 py-2.5 bg-[#97192C] text-white font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A]"
              >
                I Understand &amp; Agree
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Consent Disclosure & Submit Action */}
      <div className="bg-white border-2 border-[#120F0A] p-6 rounded-2xl shadow-[6px_6px_0px_0px_#120F0A] space-y-4">
        {/* Statutory Legal Framework Cards */}
        <div className="bg-[#FAF8F5] border-2 border-[#120F0A] p-4 rounded-xl text-left space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-[#97192C]">
              <Scale className="w-4 h-4" /> Legal Framework &amp; Enforceability
            </div>
            <button
              type="button"
              onClick={() => setShowLegalModal(true)}
              className="text-[11px] font-bold text-[#97192C] hover:underline flex items-center gap-1"
            >
              <BookOpen className="w-3.5 h-3.5" /> Read Full Disclosures
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
            <div className="bg-white border border-[#120F0A] p-2.5 rounded-lg space-y-1">
              <div className="font-bold text-[#120F0A]">📜 Section 10A IT Act 2000</div>
              <p className="text-[10px] text-[#716F6C] leading-snug">
                Electronic contracts and e-signatures are legally valid and enforceable in Indian courts.
              </p>
            </div>
            <div className="bg-white border border-[#120F0A] p-2.5 rounded-lg space-y-1">
              <div className="font-bold text-[#120F0A]">⚖️ Section 65B BSA / Evidence</div>
              <p className="text-[10px] text-[#716F6C] leading-snug">
                Immutable SHA-256 checksums, timestamps &amp; IP logs constitute primary electronic evidence.
              </p>
            </div>
            <div className="bg-white border border-[#120F0A] p-2.5 rounded-lg space-y-1">
              <div className="font-bold text-[#120F0A]">🛡️ Section 8 Non-Profit Co.</div>
              <p className="text-[10px] text-[#716F6C] leading-snug">
                Executed under GOBITSNBYTES FOUNDATION legal governance (CIN/Reg UP, India).
              </p>
            </div>
          </div>
        </div>

        {submitError && (
          <div className="bg-red-50 border-2 border-red-800 text-red-900 p-3 rounded-xl text-xs font-bold flex items-center gap-2 text-left">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{submitError}</span>
          </div>
        )}

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={agreedToTerms}
            onChange={(e) => setAgreedToTerms(e.target.checked)}
            className="mt-1 w-4 h-4 rounded border-2 border-[#120F0A] accent-[#97192C]"
          />
          <span className="text-xs text-[#413F3B] font-medium leading-relaxed text-left">
            I agree to sign this document electronically. I understand that my electronic signature is legally binding
            under Section 10A of the IT Act 2000, and that my IP address, timestamp, and verification logs will be cryptographically registered in the audit trail.
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
