"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type PortalDocument = {
  id: string;
  document_key: string;
  status: string;
  signature_url?: string | null;
};

type PortalData = {
  case_id: string;
  case_title: string;
  case_kind: string;
  participant: { name: string; email: string; role: string; status: string };
  documents: PortalDocument[];
  field_manifest: Record<string, Array<{ key: string; label: string; type: string }>>;
};

export default function OnboardingPortalClient({ token }: { token: string }) {
  const [portal, setPortal] = useState<PortalData | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | boolean>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const response = await fetch(`/api/onboarding/public/${token}`, { cache: "no-store" });
    if (!response.ok) throw new Error("This onboarding link is invalid or expired.");
    setPortal(await response.json());
  };

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message));
  }, [token]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const response = await fetch(`/api/onboarding/public/${token}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers, confirmed_identity: confirmed }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(typeof body.detail === "string" ? body.detail : "Submission failed.");
      return;
    }
    setPortal(body);
    setMessage("Saved. Complete the signature steps below to finish your packet.");
  };

  if (error && !portal) return <main className="mx-auto max-w-2xl p-8"><div className="border-2 border-red-700 bg-red-50 p-5 font-mono text-sm text-red-900">{error}</div></main>;
  if (!portal) return <main className="mx-auto max-w-2xl p-8 font-mono text-sm">Loading onboarding portal...</main>;

  const fields = Object.values(portal.field_manifest).flat();
  const submitted = portal.participant.status === "submitted";
  return (
    <main className="min-h-screen bg-[#f7f4ef] px-4 py-10 text-[#120f0a]">
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="border-2 border-black bg-[#3c0a12] p-6 text-white shadow-[6px_6px_0_#120f0a]">
          <p className="font-mono text-xs uppercase tracking-widest text-[#fc920d]">bits&bytes onboarding</p>
          <h1 className="mt-2 text-3xl font-black uppercase">{portal.case_title}</h1>
          <p className="mt-2 text-sm text-white/75">This private portal is scoped to {portal.participant.name} ({portal.participant.role}).</p>
        </header>

        {message && <div className="border-2 border-emerald-800 bg-emerald-50 p-4 font-mono text-sm text-emerald-900">{message}</div>}
        {error && <div className="border-2 border-red-700 bg-red-50 p-4 font-mono text-sm text-red-900">{error}</div>}

        {!submitted && (
          <form onSubmit={submit} className="space-y-5 border-2 border-black bg-white p-6 shadow-[4px_4px_0_#120f0a]">
            <div>
              <h2 className="text-xl font-black uppercase">Complete your details</h2>
              <p className="mt-1 text-sm text-zinc-600">Your responses are retained as source evidence and placed into the signed PDF workflow.</p>
            </div>
            {fields.map((field, index) => (
              <label key={`${field.key}-${index}`} className="block space-y-1 font-mono text-xs font-bold uppercase">
                {field.label}
                {field.type === "checkbox" ? (
                  <span className="flex items-center gap-2 normal-case"><input type="checkbox" checked={answers[field.key] === true} onChange={(event) => setAnswers((current) => ({ ...current, [field.key]: event.target.checked }))} /> I confirm this statement</span>
                ) : field.type === "signature" ? (
                  <p className="normal-case font-normal text-zinc-600">Signature is completed in the secure signing window after submission.</p>
                ) : (
                  <input required={field.key !== "track" && field.key !== "summary"} type={field.type === "date" ? "date" : "text"} value={String(answers[field.key] ?? "")} onChange={(event) => setAnswers((current) => ({ ...current, [field.key]: event.target.value }))} className="w-full border-2 border-black px-3 py-2 text-sm normal-case outline-none focus:border-[#fc920d]" />
                )}
              </label>
            ))}
            <label className="flex items-start gap-2 border-t-2 border-dashed border-zinc-300 pt-4 font-mono text-xs"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I confirm these details are mine and understand that submission creates a signature request.</label>
            <button type="submit" className="border-2 border-black bg-[#fc920d] px-5 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a]">Submit onboarding packet</button>
          </form>
        )}

        <section className="border-2 border-black bg-white p-6 shadow-[4px_4px_0_#120f0a]">
          <h2 className="text-xl font-black uppercase">Your documents</h2>
          <div className="mt-4 space-y-3">
            {portal.documents.map((document) => (
              <div key={document.id} className="flex flex-col gap-3 border-2 border-zinc-300 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div><p className="font-black uppercase">{document.document_key.replaceAll("_", " ")}</p><p className="font-mono text-xs text-zinc-600">Status: {document.status}</p></div>
                {document.signature_url ? <Link href={document.signature_url} className="border-2 border-black bg-[#3c0a12] px-4 py-2 text-center font-mono text-xs font-black uppercase text-white">Open signature window</Link> : <span className="font-mono text-xs text-zinc-500">Complete the portal form first</span>}
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
