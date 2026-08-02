"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Users, Layers, Send, ArrowRight, ArrowLeft, Plus, Trash2, CheckCircle2 } from "lucide-react";
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
    { id: "rec_1", name: "Primary Signer", email: "signer@example.com", color: PRESET_COLORS[0] },
  ]);

  // Step 3 State: Fields Placed
  const [fields, setFields] = useState<PlacedField[]>([]);
  const [selectedRecipientId, setSelectedRecipientId] = useState<string>("rec_1");

  // Step 4 State: Dispatch
  const [sending, setSending] = useState(false);

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

  const handleAddRecipient = () => {
    const idx = recipients.length;
    const newRec: RecipientConfig = {
      id: `rec_${Date.now()}`,
      name: `Signatory ${idx + 1}`,
      email: `signatory${idx + 1}@example.com`,
      color: PRESET_COLORS[idx % PRESET_COLORS.length] || "#97192C",
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
    setSending(true);

    const payload = {
      title: title || "Signature Request",
      file_path: filePath,
      recipients: recipients.map((r, i) => ({
        name: r.name,
        email: r.email,
        role: "signer",
        signing_order: i + 1,
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
    };

    try {
      const res = await fetch("/api/signatures/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        router.push("/dashboard/signatures");
      }
    } catch (e) {
      console.error("Failed to send signature request", e);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Step Header Wizard Navbar */}
      <div className="bg-white border-2 border-[#120F0A] p-4 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] flex flex-col sm:flex-row items-center justify-between gap-4">
        <h1 className="text-lg font-black text-[#120F0A]">Create Signature Request</h1>

        <div className="flex items-center gap-2 text-xs font-bold">
          <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border-2 ${step >= 1 ? "bg-[#3C0A12] text-white border-[#120F0A]" : "bg-gray-100 text-gray-400"}`}>
            <Upload className="w-3.5 h-3.5" /> 1. Document
          </div>
          <ArrowRight className="w-3 h-3 text-[#716F6C]" />
          <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border-2 ${step >= 2 ? "bg-[#3C0A12] text-white border-[#120F0A]" : "bg-gray-100 text-gray-400"}`}>
            <Users className="w-3.5 h-3.5" /> 2. Signatories
          </div>
          <ArrowRight className="w-3 h-3 text-[#716F6C]" />
          <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border-2 ${step >= 3 ? "bg-[#3C0A12] text-white border-[#120F0A]" : "bg-gray-100 text-gray-400"}`}>
            <Layers className="w-3.5 h-3.5" /> 3. Fields
          </div>
          <ArrowRight className="w-3 h-3 text-[#716F6C]" />
          <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border-2 ${step >= 4 ? "bg-[#3C0A12] text-white border-[#120F0A]" : "bg-gray-100 text-gray-400"}`}>
            <Send className="w-3.5 h-3.5" /> 4. Review
          </div>
        </div>
      </div>

      {/* Step 1: Upload Dropzone */}
      {step === 1 && (
        <div className="bg-white border-2 border-[#120F0A] rounded-2xl p-10 shadow-[6px_6px_0px_0px_#120F0A] text-center space-y-6">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-[#FEE9CF] border-2 border-[#120F0A] mx-auto flex items-center justify-center text-[#97192C]">
              <Upload className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-black text-[#120F0A]">Upload Document for Signature</h2>
            <p className="text-xs text-[#716F6C]">Select a PDF or Microsoft Word (.docx) contract file to begin placing signature fields.</p>

            <label className="inline-flex items-center gap-2 px-6 py-3 bg-[#FC920D] text-[#120F0A] font-bold text-xs border-2 border-[#120F0A] rounded-xl shadow-[3px_3px_0px_0px_#120F0A] cursor-pointer hover:translate-y-[-2px] transition-all">
              {uploading ? "Processing Document..." : "Choose File (.pdf, .docx)"}
              <input type="file" accept=".pdf,.docx,.doc" onChange={handleFileUpload} className="hidden" />
            </label>
          </div>
        </div>
      )}

      {/* Step 2: Configure Signatories */}
      {step === 2 && (
        <div className="bg-white border-2 border-[#120F0A] rounded-2xl p-6 shadow-[6px_6px_0px_0px_#120F0A] space-y-6">
          <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-4">
            <div>
              <h2 className="text-lg font-black text-[#120F0A]">Add Signatories</h2>
              <p className="text-xs text-[#716F6C]">Specify who needs to review and sign this document.</p>
            </div>
            <button
              type="button"
              onClick={handleAddRecipient}
              className="flex items-center gap-1.5 px-3 py-2 bg-white border-2 border-[#120F0A] rounded-lg text-xs font-bold text-[#120F0A] shadow-[2px_2px_0px_0px_#120F0A]"
            >
              <Plus className="w-4 h-4" /> Add Signatory
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#716F6C] mb-1">Contract Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-bold"
              />
            </div>

            <div className="space-y-3">
              {recipients.map((r, idx) => (
                <div key={r.id} className="flex flex-col sm:flex-row items-center gap-3 p-3 border-2 border-[#120F0A] rounded-xl bg-[#FAF8F5]">
                  <span className="w-4 h-4 rounded-full border border-[#120F0A]" style={{ backgroundColor: r.color }} />
                  <span className="text-xs font-bold text-[#716F6C]">#{idx + 1}</span>
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
                    className="flex-1 px-3 py-1.5 bg-white border-2 border-[#120F0A] rounded-lg text-xs font-bold"
                  />
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
                    className="flex-1 px-3 py-1.5 bg-white border-2 border-[#120F0A] rounded-lg text-xs font-bold"
                  />
                  {recipients.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveRecipient(r.id)}
                      className="p-1.5 bg-red-100 text-red-700 border border-red-700 rounded-lg hover:bg-red-200"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t-2 border-[#120F0A]">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="flex items-center gap-1.5 px-4 py-2 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-bold"
            >
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
            <button
              type="button"
              onClick={() => setStep(3)}
              className="flex items-center gap-1.5 px-6 py-2 bg-[#FC920D] text-[#120F0A] border-2 border-[#120F0A] rounded-xl text-xs font-bold shadow-[2px_2px_0px_0px_#120F0A]"
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

          <div className="flex justify-between p-4 bg-white border-2 border-[#120F0A] rounded-xl shadow-[4px_4px_0px_0px_#120F0A]">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="flex items-center gap-1.5 px-4 py-2 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-bold"
            >
              <ArrowLeft className="w-4 h-4" /> Back to Signatories
            </button>
            <button
              type="button"
              onClick={() => setStep(4)}
              className="flex items-center gap-1.5 px-6 py-2 bg-[#FC920D] text-[#120F0A] border-2 border-[#120F0A] rounded-xl text-xs font-bold shadow-[2px_2px_0px_0px_#120F0A]"
            >
              Next: Review & Send <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Final Review & Dispatch */}
      {step === 4 && (
        <div className="bg-white border-2 border-[#120F0A] rounded-2xl p-6 shadow-[6px_6px_0px_0px_#120F0A] space-y-6">
          <div className="space-y-2">
            <h2 className="text-lg font-black text-[#120F0A]">Review & Dispatch Request</h2>
            <p className="text-xs text-[#716F6C]">Verify signature contract details before sending out tokenized signature links.</p>
          </div>

          <div className="bg-[#FAF8F5] border-2 border-[#120F0A] rounded-xl p-4 space-y-3 text-xs font-medium">
            <div>
              <span className="font-bold text-[#716F6C]">Document Title:</span>
              <div className="text-sm font-bold text-[#120F0A]">{title}</div>
            </div>
            <div>
              <span className="font-bold text-[#716F6C]">Signatories ({recipients.length}):</span>
              <div className="space-y-1 mt-1">
                {recipients.map((r) => (
                  <div key={r.id} className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
                    <span className="font-bold text-[#120F0A]">{r.name}</span>
                    <span className="text-[#716F6C]">(&lt;{r.email}&gt;)</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <span className="font-bold text-[#716F6C]">Interactive Fields Placed:</span>
              <div className="font-bold text-[#120F0A]">{fields.length} placed elements across {previews.length} pages</div>
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t-2 border-[#120F0A]">
            <button
              type="button"
              onClick={() => setStep(3)}
              className="flex items-center gap-1.5 px-4 py-2 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-bold"
            >
              <ArrowLeft className="w-4 h-4" /> Edit Fields
            </button>
            <button
              type="button"
              disabled={sending}
              onClick={handleDispatch}
              className="flex items-center gap-2 px-6 py-2.5 bg-[#97192C] text-white border-2 border-[#120F0A] rounded-xl text-xs font-bold shadow-[3px_3px_0px_0px_#120F0A] hover:translate-y-[-1px] transition-all disabled:opacity-50"
            >
              <Send className="w-4 h-4" /> {sending ? "Dispatching Links..." : "Finalize & Send Links"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
