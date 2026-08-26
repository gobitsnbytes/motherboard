"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Users, Layers, Send, ArrowRight, ArrowLeft, Plus, Trash2, CheckCircle2, FileText, UserCheck, Mail } from "lucide-react";
import { DocumentEditor, RecipientConfig, PlacedField } from "../../../../components/signatures/DocumentEditor";

const PRESET_COLORS = ["#97192C", "#FC920D", "#2563EB", "#059669", "#7C3AED"] as const;

export default function SignatureBuilderPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Step 1 State: Upload
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [fileId, setFileId] = useState("");
  const [filePath, setFilePath] = useState("");
  const [previews, setPreviews] = useState<string[]>([]);
  const [title, setTitle] = useState("");

  // Step 2 State: Signatories
  const [recipients, setRecipients] = useState<RecipientConfig[]>([
    { id: "rec_1", name: "Primary Signer", email: "signer@example.com", color: PRESET_COLORS[0], requires_otp: false },
  ]);

  // Step 3 State: Fields Placed
  const [fields, setFields] = useState<PlacedField[]>([]);
  const [orgCountersign, setOrgCountersign] = useState(false);
  const [selectedRecipientId, setSelectedRecipientId] = useState<string>("rec_1");

  // Step 4 State: Dispatch
  const [sending, setSending] = useState(false);
  const [idempotencyKey] = useState(() => `idemp_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setFile(selected);
    setTitle(selected.name.replace(/\.[^/.]+$/, ""));
    setUploading(true);

    const formData = new FormData();
    formData.append("file", selected);

    try {
      const res = await fetch("/api/signatures/upload", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setFileId(data.file_id);
        setFilePath(data.file_path);
        setPreviews(data.previews);
        setStep(2);
      }
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setUploading(false);
    }
  };

  const handleSignMyselfPreset = () => {
    setRecipients([
      { id: "rec_self", name: "Authorized Signatory", email: "legal@gobitsnbytes.org", color: PRESET_COLORS[0], requires_otp: false }
    ]);
    setSelectedRecipientId("rec_self");
  };

  const handleAddRecipient = () => {
    const idx = recipients.length;
    const newRec: RecipientConfig = {
      id: `rec_${Date.now()}`,
      name: `Signatory ${idx + 1}`,
      email: `signatory${idx + 1}@example.com`,
      color: PRESET_COLORS[idx % PRESET_COLORS.length] || "#97192C",
      requires_otp: false,
    };
    setRecipients([...recipients, newRec]);
  };

  const handleRemoveRecipient = (id: string) => {
    if (recipients.length <= 1) return;
    setRecipients(recipients.filter((r) => r.id !== id));
    setFields(fields.filter((f) => f.recipient_id !== id));
    if (selectedRecipientId === id && recipients[0]) {
      setSelectedRecipientId(recipients[0].id);
    }
  };

  const handleDispatch = async () => {
    if (sending) return;
    setSending(true);

    const payload = {
      title: title || "Signature Request",
      file_path: filePath,
      idempotency_key: idempotencyKey,
      recipients: recipients.map((r, i) => ({
        id: r.id,
        name: r.name,
        email: r.email,
        role: "signer",
        signing_order: i + 1,
        requires_otp: Boolean(r.requires_otp),
      })),
      fields: fields.map((f) => ({
        recipient_id: f.recipient_id,
        type: f.type,
        page_number: f.page_number,
        pos_x: f.pos_x,
        pos_y: f.pos_y,
        width: f.width,
        height: f.height,
        required: f.required,
      })),
      expires_in_days: 30,
      requires_org_countersign: orgCountersign,
    };

    try {
      const res = await fetch("/api/signatures/requests", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        router.push("/dashboard/signatures");
      } else {
        const errData = await res.json().catch(() => null);
        console.error("Failed to send signature request:", res.status, errData);
        alert(`Failed to send request (${res.status}): ${errData?.detail || "Server error"}`);
      }
    } catch (e) {
      console.error("Failed to send signature request", e);
      alert("Network error: Could not reach server to send signature request.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
      {/* Wizard Header Bar */}
      <div className="bg-[#141418] border-2 border-border p-4 rounded-base shadow-dark flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-heading font-black text-white uppercase tracking-tight">Create Signature Request</h1>
          <p className="text-xs text-zinc-400 font-mono">Step {step} of 4 &bull; Configure contract workflow</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs font-mono font-bold">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base border-2 transition-all ${step >= 1 ? "bg-orange text-black border-black shadow-light" : "bg-[#181820] text-zinc-400 border-border"}`}>
            <Upload className="w-3.5 h-3.5" /> 1. Document
          </div>
          <ArrowRight className="w-3 h-3 text-zinc-500" />
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base border-2 transition-all ${step >= 2 ? "bg-orange text-black border-black shadow-light" : "bg-[#181820] text-zinc-400 border-border"}`}>
            <Users className="w-3.5 h-3.5" /> 2. Signatories
          </div>
          <ArrowRight className="w-3 h-3 text-zinc-500" />
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base border-2 transition-all ${step >= 3 ? "bg-orange text-black border-black shadow-light" : "bg-[#181820] text-zinc-400 border-border"}`}>
            <Layers className="w-3.5 h-3.5" /> 3. Fields
          </div>
          <ArrowRight className="w-3 h-3 text-zinc-500" />
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base border-2 transition-all ${step >= 4 ? "bg-orange text-black border-black shadow-light" : "bg-[#181820] text-zinc-400 border-border"}`}>
            <Send className="w-3.5 h-3.5" /> 4. Review
          </div>
        </div>
      </div>

      {/* Step 1: Document Upload */}
      {step === 1 && (
        <div className="bg-[#141418] border-2 border-border rounded-base p-8 sm:p-12 shadow-dark text-center space-y-6">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-16 h-16 rounded-base bg-orange/20 border-2 border-border mx-auto flex items-center justify-center text-orange shadow-light">
              <Upload className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-heading font-black text-white uppercase tracking-tight">Upload Document for Signature</h2>
            <p className="text-xs text-zinc-300 font-base leading-relaxed">
              Select a PDF or Word (.docx) document to convert into an interactive, legally-binding digital contract.
            </p>

            <label className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-orange text-black font-heading font-black text-xs uppercase tracking-wider border-2 border-black rounded-base shadow-light cursor-pointer hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all">
              {uploading ? "Processing & Converting PDF..." : "Choose File (.pdf, .docx)"}
              <input type="file" accept=".pdf,.docx,.doc" onChange={handleFileUpload} className="hidden" />
            </label>
          </div>
        </div>
      )}

      {/* Step 2: Configure Signatories */}
      {step === 2 && (
        <div className="bg-[#141418] border-2 border-border rounded-base p-6 sm:p-8 shadow-dark space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b-2 border-border pb-4">
            <div>
              <h2 className="text-lg font-heading font-black text-white uppercase tracking-tight">Add Signatories</h2>
              <p className="text-xs text-zinc-400 font-mono">Specify recipient names and email addresses who need to sign.</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSignMyselfPreset}
                className="flex items-center gap-1.5 px-3 py-2 bg-main text-white border-2 border-border rounded-base text-xs font-mono font-bold shadow-light"
              >
                <UserCheck className="w-4 h-4" /> Sign Myself
              </button>
              <button
                type="button"
                onClick={handleAddRecipient}
                className="flex items-center gap-1.5 px-3 py-2 bg-[#181820] text-zinc-200 border-2 border-border rounded-base text-xs font-mono font-bold shadow-light"
              >
                <Plus className="w-4 h-4" /> Add Signatory
              </button>
            </div>
          </div>

          <div className="space-y-5">
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-zinc-300 mb-1.5">
                Contract Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Non-Disclosure Agreement 2026"
                className="w-full px-4 py-2.5 bg-black border-2 border-border rounded-base text-xs font-mono text-white shadow-light focus:outline-none focus:border-orange"
              />
            </div>

            <div className="space-y-3">
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-zinc-300">
                Signatories List ({recipients.length})
              </label>
              {recipients.map((r, idx) => (
                <div key={r.id} className="p-4 border-2 border-border rounded-base bg-[#181820] shadow-light space-y-3 text-left">
                  {/* Top Header Row */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-4 h-4 rounded-base border border-border" style={{ backgroundColor: r.color }} />
                      <span className="text-xs font-mono font-bold text-white">Signatory #{idx + 1}</span>
                    </div>
                    {recipients.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveRecipient(r.id)}
                        className="px-2.5 py-1 bg-red-950 text-red-300 border border-red-800 rounded-base hover:bg-red-900 transition-colors text-xs font-mono font-bold flex items-center gap-1"
                        title="Remove Signatory"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Remove
                      </button>
                    )}
                  </div>

                  {/* Inputs Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] font-mono font-bold uppercase text-zinc-400 mb-1">Full Name</label>
                      <input
                        type="text"
                        placeholder="Signatory Name"
                        value={r.name}
                        onChange={(e) => {
                          const updated = [...recipients];
                          if (updated[idx]) {
                            updated[idx].name = e.target.value;
                            setRecipients(updated);
                          }
                        }}
                        className="w-full px-3 py-2 bg-black border-2 border-border rounded-base text-xs font-mono text-white focus:outline-none focus:border-orange"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono font-bold uppercase text-zinc-400 mb-1">Email Address</label>
                      <input
                        type="email"
                        placeholder="Signatory Email"
                        value={r.email}
                        onChange={(e) => {
                          const updated = [...recipients];
                          if (updated[idx]) {
                            updated[idx].email = e.target.value;
                            setRecipients(updated);
                          }
                        }}
                        className="w-full px-3 py-2 bg-black border-2 border-border rounded-base text-xs font-mono text-white focus:outline-none focus:border-orange"
                      />
                    </div>
                  </div>

                  {/* Security & Verification Options */}
                  <div className="pt-2 border-t border-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer font-mono font-bold text-zinc-300">
                      <input
                        type="checkbox"
                        checked={r.requires_otp || false}
                        onChange={(e) => {
                          const updated = [...recipients];
                          if (updated[idx]) {
                            updated[idx].requires_otp = e.target.checked;
                            setRecipients(updated);
                          }
                        }}
                        className="w-4 h-4 rounded border-2 border-border accent-orange"
                      />
                      <span>Require 6-Digit Email OTP Verification</span>
                    </label>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] font-mono font-bold uppercase text-zinc-400">Security Mode:</span>
                      <select
                        value={r.allowed_sig_type || "any"}
                        onChange={(e) => {
                          const updated = [...recipients];
                          if (updated[idx]) {
                            updated[idx].allowed_sig_type = e.target.value;
                            setRecipients(updated);
                          }
                        }}
                        className="px-2.5 py-1.5 bg-black border-2 border-border rounded-base text-[11px] font-mono font-bold text-white focus:outline-none focus:border-orange"
                      >
                        <option value="any">DSC (if available) or Simple OTP (Default)</option>
                        <option value="dsc_only">Enforce Class 1/2/3 DSC Only</option>
                        <option value="email_only">Enforce Simple Email OTP Only</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t-2 border-border">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#181820] border-2 border-border rounded-base text-xs font-mono font-bold text-zinc-200 shadow-light"
            >
              <ArrowLeft className="w-4 h-4" /> Back to Upload
            </button>
            <button
              type="button"
              onClick={() => setStep(3)}
              className="flex items-center gap-1.5 px-6 py-2.5 bg-orange text-black border-2 border-black rounded-base text-xs font-heading font-black uppercase tracking-wider shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
            >
              Next: Place Fields <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Interactive Visual Canvas Field Placement */}
      {step === 3 && (
        <div className="space-y-4">
          <DocumentEditor
            previews={previews}
            recipients={recipients}
            fields={fields}
            onChangeFields={setFields}
            selectedRecipientId={selectedRecipientId}
            onSelectRecipient={setSelectedRecipientId}
          />

          <div className="flex justify-between p-4 bg-[#141418] border-2 border-border rounded-base shadow-dark">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#181820] border-2 border-border rounded-base text-xs font-mono font-bold text-zinc-200 shadow-light"
            >
              <ArrowLeft className="w-4 h-4" /> Back to Signatories
            </button>
            <button
              type="button"
              onClick={() => setStep(4)}
              className="flex items-center gap-1.5 px-6 py-2.5 bg-orange text-black border-2 border-black rounded-base text-xs font-heading font-black uppercase tracking-wider shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
            >
              Next: Review &amp; Dispatch <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Final Review & Dispatch */}
      {step === 4 && (
        <div className="bg-[#141418] border-2 border-border rounded-base p-6 sm:p-8 shadow-dark space-y-6">
          <div className="space-y-1 border-b-2 border-border pb-4">
            <h2 className="text-lg font-heading font-black text-white uppercase tracking-tight">Review &amp; Dispatch Contract</h2>
            <p className="text-xs text-zinc-400 font-mono">Verify signature contract details before sending out tokenized signature links.</p>
          </div>

          <div className="bg-[#181820] border-2 border-border rounded-base p-5 space-y-4 text-xs font-mono shadow-light">
            <div>
              <span className="font-bold text-zinc-400 uppercase tracking-wider text-[10px]">Contract Title:</span>
              <div className="text-base font-black text-white font-heading mt-0.5">{title}</div>
            </div>
            <div>
              <span className="font-bold text-zinc-400 uppercase tracking-wider text-[10px]">Signatories ({recipients.length}):</span>
              <div className="space-y-2 mt-1.5">
                {recipients.map((r) => (
                  <div key={r.id} className="flex items-center gap-2 text-xs font-bold text-white">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>{r.name}</span>
                    <span className="text-zinc-400 font-mono text-[11px]">&lt;{r.email}&gt;</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <span className="font-bold text-zinc-400 uppercase tracking-wider text-[10px]">Placed Fields Summary:</span>
              <div className="font-bold text-zinc-200 mt-0.5">{fields.length} interactive fields placed across {previews.length} document pages</div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t-2 border-border">
            <button
              type="button"
              onClick={() => setStep(3)}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#181820] border-2 border-border rounded-base text-xs font-mono font-bold text-zinc-200 shadow-light"
            >
              <ArrowLeft className="w-4 h-4" /> Edit Placed Fields
            </button>
            <label className="flex cursor-pointer items-center gap-2 rounded-base border-2 border-border bg-[#181820] px-4 py-2.5 text-xs font-mono font-bold text-white shadow-light">
              <input
                type="checkbox"
                checked={orgCountersign}
                onChange={(e) => setOrgCountersign(e.target.checked)}
                className="size-4 accent-orange"
              />
              Org counter-sign (legal@gobitsnbytes.org)
            </label>
            <button
              type="button"
              disabled={sending}
              onClick={handleDispatch}
              className="flex items-center gap-2 px-6 py-3 bg-orange text-black border-2 border-black rounded-base text-xs font-heading font-black uppercase tracking-wider shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all disabled:opacity-50"
            >
              <Send className="w-4 h-4" /> {sending ? "Dispatching Email Links..." : "Finalize & Send Links"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
