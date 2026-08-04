"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck, RefreshCw, CheckCircle2, Lock, FileSignature, Key, Plus, Search, AlertCircle } from "lucide-react";

interface Signer {
  name: string;
  email: string;
  signed: boolean;
  signed_at?: string;
}

interface Envelope {
  envelope_id: string;
  title: string;
  document_type: string;
  content: string;
  signers: Signer[];
  status: string;
  created_at: string;
  sha256_seal?: string;
  sealed_at?: string;
}

interface Stats {
  total_envelopes: number;
  pending_signature: number;
  sealed_and_locked: number;
  verification_rate: number;
}

interface VerificationResult {
  is_valid: boolean;
  envelope_id: string;
  title: string;
  status: string;
  sealed_at?: string;
  sha256_hash: string;
  verification_message: string;
}

export default function SignaturesVaultUI() {
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Modal & Verification state
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [verifyHashInput, setVerifyHashInput] = useState("");
  const [verificationResult, setVerificationResult] = useState<VerificationResult | null>(null);

  // Form
  const [draftForm, setDraftForm] = useState({
    title: "",
    document_type: "MOU",
    content: "",
    signer_name: "",
    signer_email: "",
  });

  const fetchVaultData = async () => {
    setLoading(true);
    try {
      const [envRes, statsRes] = await Promise.all([
        fetch("/api/plugins/signatures_vault/envelopes"),
        fetch("/api/plugins/signatures_vault/stats"),
      ]);

      if (envRes.ok) setEnvelopes(await envRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (err) {
      console.error("Failed to load signatures vault data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVaultData();
  }, []);

  const handleCreateEnvelope = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading("draft");
    try {
      const res = await fetch("/api/plugins/signatures_vault/envelopes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: draftForm.title,
          document_type: draftForm.document_type,
          content: draftForm.content,
          signers: [{ name: draftForm.signer_name, email: draftForm.signer_email }],
        }),
      });
      if (res.ok) {
        setShowDraftModal(false);
        setDraftForm({ title: "", document_type: "MOU", content: "", signer_name: "", signer_email: "" });
        await fetchVaultData();
      }
    } catch (err) {
      console.error("Draft envelope failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSign = async (envId: string, email: string) => {
    setActionLoading(`sign-${envId}`);
    try {
      const res = await fetch(`/api/plugins/signatures_vault/envelopes/${envId}/sign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signer_email: email, signature_token: "VALID_TOKEN" }),
      });
      if (res.ok) {
        await fetchVaultData();
      }
    } catch (err) {
      console.error("Sign envelope failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSeal = async (envId: string) => {
    setActionLoading(`seal-${envId}`);
    try {
      const res = await fetch(`/api/plugins/signatures_vault/envelopes/${envId}/seal`, { method: "POST" });
      if (res.ok) {
        await fetchVaultData();
      }
    } catch (err) {
      console.error("Seal envelope failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleVerifySeal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifyHashInput.trim()) return;
    setActionLoading("verify");
    try {
      const isHash = verifyHashInput.length > 30;
      const res = await fetch("/api/plugins/signatures_vault/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          isHash ? { sha256_seal: verifyHashInput.trim() } : { envelope_id: verifyHashInput.trim() }
        ),
      });
      if (res.ok) {
        setVerificationResult(await res.json());
      }
    } catch (err) {
      console.error("Verification failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 border-4 border-border bg-main/5 rounded-base shadow-light">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center p-3 border-2 border-border bg-main rounded-base text-main-foreground shadow-light">
            <ShieldCheck className="size-6" />
          </div>
          <div>
            <h2 className="text-xl font-heading font-bold text-foreground">
              Legal Signatures & Cryptographic Seal Vault
            </h2>
            <p className="text-xs text-muted-foreground font-base mt-0.5">
              Legal signature workflow, envelope status tracking, & immutable SHA-256 seal verification.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchVaultData}
            disabled={loading}
            className="flex items-center gap-2 border-2 border-border bg-bg text-foreground px-3.5 py-2 text-xs font-bold rounded-base hover:bg-main/10 transition-all"
          >
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={() => setShowDraftModal(true)}
            className="flex items-center gap-2 border-2 border-border bg-main text-main-foreground px-4 py-2 text-xs font-bold rounded-base hover:bg-main/90 shadow-light transition-all hover:translate-x-[2px] hover:translate-y-[2px]"
          >
            <Plus className="size-4" />
            Draft Envelope
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Total Envelopes</span>
            <FileSignature className="size-4 text-main" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2 font-mono">
            {stats ? stats.total_envelopes : "-"}
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Pending Signatures</span>
            <Key className="size-4 text-amber-500" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2 font-mono">
            {stats ? stats.pending_signature : "-"}
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Cryptographically Sealed</span>
            <Lock className="size-4 text-green-500" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2 font-mono">
            {stats ? stats.sealed_and_locked : "-"}
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>SHA-256 Integrity</span>
            <CheckCircle2 className="size-4 text-green-500" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2 font-mono">
            {stats ? `${stats.verification_rate}%` : "-"}
          </div>
        </div>
      </div>

      {/* SHA-256 Seal Verification Tool */}
      <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light">
        <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
          <Search className="size-4 text-main" />
          SHA-256 Cryptographic Seal Verifier
        </h3>
        <form onSubmit={handleVerifySeal} className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={verifyHashInput}
            onChange={(e) => setVerifyHashInput(e.target.value)}
            placeholder="Paste SHA-256 Seal Digest or Envelope ID (e.g. env-aoa-2026-lko)"
            className="flex-1 border-2 border-border p-2.5 rounded-base bg-bg font-mono text-xs text-foreground"
          />
          <button
            type="submit"
            disabled={actionLoading === "verify"}
            className="border-2 border-border bg-main text-main-foreground px-5 py-2.5 text-xs font-bold rounded-base hover:bg-main/90 shadow-light"
          >
            Verify Seal
          </button>
        </form>

        {verificationResult && (
          <div
            className={`mt-4 border-2 border-border p-4 rounded-base text-xs font-mono ${
              verificationResult.is_valid ? "bg-green-500/10 text-green-700" : "bg-red-500/10 text-red-700"
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-sm mb-1 font-heading">
              {verificationResult.is_valid ? (
                <>
                  <CheckCircle2 className="size-5 text-green-600" />
                  VERIFIED SEAL: {verificationResult.title}
                </>
              ) : (
                <>
                  <AlertCircle className="size-5 text-red-600" />
                  SEAL VERIFICATION FAILED
                </>
              )}
            </div>
            <div>{verificationResult.verification_message}</div>
            {verificationResult.is_valid && (
              <div className="mt-2 text-[10px] text-foreground font-semibold flex flex-col gap-1">
                <div>Envelope ID: {verificationResult.envelope_id}</div>
                <div>Status: {verificationResult.status}</div>
                <div>Sealed At: {verificationResult.sealed_at}</div>
                <div className="break-all font-mono text-muted-foreground">Digest: {verificationResult.sha256_hash}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Envelopes Table */}
      <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light overflow-x-auto">
        <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider mb-4">
          Legal Envelope Registry
        </h3>

        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b-2 border-border bg-main/10 font-heading text-foreground">
              <th className="p-3">Envelope ID / Title</th>
              <th className="p-3">Document Type</th>
              <th className="p-3">Signers & Progress</th>
              <th className="p-3">SHA-256 Seal Hash</th>
              <th className="p-3">Status</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {envelopes.map((env) => {
              const signedCount = env.signers.filter((s) => s.signed).length;
              const pendingSigner = env.signers.find((s) => !s.signed);

              return (
                <tr key={env.envelope_id} className="border-b border-border/50 hover:bg-main/5">
                  <td className="p-3 font-bold font-mono">
                    <div className="text-sm font-bold text-foreground font-sans">{env.title}</div>
                    <div className="text-[10px] text-muted-foreground">{env.envelope_id}</div>
                  </td>
                  <td className="p-3 font-semibold text-foreground">{env.document_type}</td>
                  <td className="p-3">
                    <div className="font-bold text-foreground">
                      {signedCount} / {env.signers.length} Signed
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {env.signers.map((s, idx) => (
                        <span
                          key={idx}
                          className={`text-[9px] px-1.5 py-0.5 rounded border ${
                            s.signed ? "bg-green-500/20 text-green-800 font-bold" : "bg-amber-500/20 text-amber-800"
                          }`}
                        >
                          {s.name} ({s.signed ? "✓" : "Pending"})
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="p-3 font-mono text-[10px] text-muted-foreground break-all max-w-[180px]">
                    {env.sha256_seal ? (
                      <span className="text-green-700 font-bold">{env.sha256_seal.slice(0, 16)}...</span>
                    ) : (
                      "Not Sealed"
                    )}
                  </td>
                  <td className="p-3">
                    <span
                      className={`px-2.5 py-1 rounded-base font-bold text-[10px] border border-border ${
                        env.status === "SEALED"
                          ? "bg-green-500/20 text-green-700"
                          : env.status === "SIGNED"
                          ? "bg-blue-500/20 text-blue-700"
                          : "bg-amber-500/20 text-amber-700"
                      }`}
                    >
                      {env.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {pendingSigner && env.status !== "SEALED" && (
                        <button
                          onClick={() => handleSign(env.envelope_id, pendingSigner.email)}
                          disabled={actionLoading === `sign-${env.envelope_id}`}
                          className="px-2.5 py-1 text-[10px] font-bold border-2 border-border bg-main text-main-foreground rounded-base"
                        >
                          Sign ({pendingSigner.name.split(" ")[0]})
                        </button>
                      )}
                      {env.status !== "SEALED" && (
                        <button
                          onClick={() => handleSeal(env.envelope_id)}
                          disabled={actionLoading === `seal-${env.envelope_id}`}
                          className="px-2.5 py-1 text-[10px] font-bold border-2 border-border bg-green-500 text-black rounded-base"
                        >
                          Seal & Hash
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Draft Envelope Modal */}
      {showDraftModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="border-4 border-border bg-bg p-6 rounded-base shadow-light w-full max-w-md">
            <h3 className="text-lg font-heading font-bold text-foreground mb-4">Draft Legal Envelope</h3>
            <form onSubmit={handleCreateEnvelope} className="flex flex-col gap-3 text-xs">
              <div>
                <label className="font-bold block mb-1">Document Title</label>
                <input
                  required
                  type="text"
                  value={draftForm.title}
                  onChange={(e) => setDraftForm({ ...draftForm, title: e.target.value })}
                  placeholder="e.g. Regional Event Partnership Agreement"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Document Type</label>
                <select
                  value={draftForm.document_type}
                  onChange={(e) => setDraftForm({ ...draftForm, document_type: e.target.value })}
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-bold"
                >
                  <option value="e-AOA Charter">e-AOA Charter</option>
                  <option value="MOU">MOU</option>
                  <option value="NDA">NDA</option>
                  <option value="Grant Contract">Grant Contract</option>
                </select>
              </div>

              <div>
                <label className="font-bold block mb-1">Document Content Summary / Body</label>
                <textarea
                  required
                  rows={3}
                  value={draftForm.content}
                  onChange={(e) => setDraftForm({ ...draftForm, content: e.target.value })}
                  placeholder="Legal agreement text content..."
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Primary Signer Full Name</label>
                <input
                  required
                  type="text"
                  value={draftForm.signer_name}
                  onChange={(e) => setDraftForm({ ...draftForm, signer_name: e.target.value })}
                  placeholder="Signer Full Name"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Primary Signer Email</label>
                <input
                  required
                  type="email"
                  value={draftForm.signer_email}
                  onChange={(e) => setDraftForm({ ...draftForm, signer_email: e.target.value })}
                  placeholder="signer@gobitsnbytes.org"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div className="flex justify-end gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => setShowDraftModal(false)}
                  className="px-4 py-2 border-2 border-border bg-bg font-bold rounded-base"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === "draft"}
                  className="px-4 py-2 border-2 border-border bg-main text-main-foreground font-bold rounded-base"
                >
                  Dispatch Envelope
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
