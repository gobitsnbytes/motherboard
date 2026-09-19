"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import OnboardingDocumentEditor from "./OnboardingDocumentEditor";

type PortalDocument = { id: string; document_key: string; status: string; current_revision: number; signature_url?: string | null };
type PortalData = { case_title: string; participant: { name: string; role: string; status: string }; documents: PortalDocument[] };

const statusTone: Record<string, string> = {
  changes_requested: "border-amber-800 bg-amber-50 text-amber-950",
  review_requested: "border-blue-800 bg-blue-50 text-blue-950",
  approved: "border-emerald-800 bg-emerald-50 text-emerald-950",
  completed: "border-emerald-800 bg-emerald-50 text-emerald-950",
};

export default function OnboardingPortalClient({ token }: { token: string }) {
  const [portal, setPortal] = useState<PortalData | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await fetch(`/api/onboarding/public/${token}`, { cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "This onboarding link is invalid or expired.");
    setPortal(body as PortalData);
  }, [token]);

  useEffect(() => { load().catch((reason: Error) => setError(reason.message)); }, [load]);

  if (error && !portal) return <main className="mx-auto max-w-3xl p-6 sm:p-10"><div role="alert" className="border-2 border-red-800 bg-red-50 p-5 text-sm text-red-950">{error}</div></main>;
  if (!portal) return <main className="mx-auto max-w-3xl p-8 font-mono text-sm" role="status">Loading your onboarding workspace…</main>;
  if (selectedDocumentId) return <main className="min-h-screen bg-[#f7f4ef] px-4 py-6 text-[#120f0a] sm:py-10"><div className="mx-auto max-w-5xl"><OnboardingDocumentEditor token={token} documentId={selectedDocumentId} onBack={() => setSelectedDocumentId(null)} onChanged={() => void load()} /></div></main>;

  const completed = portal.documents.filter((document) => document.status === "completed").length;
  return <main className="min-h-screen bg-[#f7f4ef] px-4 py-10 text-[#120f0a]">
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="border-2 border-black bg-[#3c0a12] p-6 text-white shadow-[6px_6px_0_#120f0a] sm:p-8">
        <p className="font-mono text-xs uppercase tracking-widest text-[#fc920d]">bits&amp;bytes onboarding workspace</p>
        <h1 className="mt-2 text-3xl font-black uppercase sm:text-4xl">{portal.case_title}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-white/75">Welcome, {portal.participant.name}. Complete each document, send revisions to HQ, and respond to review comments here.</p>
        <div className="mt-5 flex items-center gap-3"><div className="h-3 flex-1 overflow-hidden border-2 border-white bg-white/15" role="progressbar" aria-label="Packet completion" aria-valuemin={0} aria-valuemax={portal.documents.length} aria-valuenow={completed}><div className="h-full bg-[#fc920d]" style={{ width: portal.documents.length ? `${completed / portal.documents.length * 100}%` : "0%" }} /></div><span className="font-mono text-xs font-black">{completed}/{portal.documents.length}</span></div>
      </header>
      {error ? <div role="alert" className="border-2 border-red-800 bg-red-50 p-4 text-sm text-red-950">{error}</div> : null}
      <section aria-labelledby="documents-heading">
        <div className="mb-3 flex items-end justify-between gap-4"><div><p className="font-mono text-xs font-bold uppercase tracking-widest text-[#97192c]">Your packet</p><h2 id="documents-heading" className="text-2xl font-black uppercase">Documents</h2></div><span className="font-mono text-xs uppercase">{portal.participant.status.replaceAll("_", " ")}</span></div>
        <div className="grid gap-4 sm:grid-cols-2">{portal.documents.map((document, index) => {
          const canEdit = ["awaiting_completion", "draft", "changes_requested"].includes(document.status);
          const tone = statusTone[document.status] ?? "border-zinc-500 bg-white text-zinc-900";
          return <article key={document.id} className="flex min-h-56 flex-col border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a]"><div className="flex items-start justify-between gap-3"><span className="grid size-9 place-items-center border-2 border-black bg-[#fc920d] font-black">{index + 1}</span><span className={`border-2 px-2 py-1 font-mono text-[10px] font-black uppercase ${tone}`}>{document.status.replaceAll("_", " ")}</span></div><h3 className="mt-5 text-xl font-black uppercase">{document.document_key.replaceAll("_", " ")}</h3><p className="mt-1 font-mono text-xs text-zinc-500">Revision {document.current_revision || "not started"}</p><p className="mt-3 flex-1 text-sm text-zinc-600">{document.status === "changes_requested" ? "HQ left review comments. Open the document to address them and submit a new revision." : document.status === "review_requested" ? "This revision is locked while HQ reviews it." : document.status === "approved" ? "Approved. HQ controls when the final document is compiled." : canEdit ? "Fill the original template in your browser. Progress saves automatically." : "Open the document to view its state and review history."}</p><div className="mt-5 flex gap-2"><button type="button" onClick={() => setSelectedDocumentId(document.id)} className="flex-1 border-2 border-black bg-[#3c0a12] px-4 py-3 font-mono text-xs font-black uppercase text-white focus:outline-none focus:ring-4 focus:ring-[#fc920d]/40">{canEdit ? "Open and fill" : "View document"}</button>{document.signature_url ? <Link href={document.signature_url} className="border-2 border-black bg-[#fc920d] px-4 py-3 font-mono text-xs font-black uppercase focus:ring-4 focus:ring-[#fc920d]/40">Sign</Link> : null}</div></article>;
        })}</div>
      </section>
      <aside className="border-2 border-black bg-white p-5 text-sm leading-6"><h2 className="font-black uppercase">How review works</h2><ol className="mt-3 grid gap-3 sm:grid-cols-3"><li><strong>1. Fill and submit.</strong><br />HQ receives a frozen revision.</li><li><strong>2. Address comments.</strong><br />Requested changes reopen only the relevant document.</li><li><strong>3. HQ finalizes.</strong><br />PDF compilation happens only after approval and signing.</li></ol></aside>
    </div>
  </main>;
}
