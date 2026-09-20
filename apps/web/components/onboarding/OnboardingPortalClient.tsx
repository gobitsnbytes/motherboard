"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import OnboardingDocumentEditor from "./OnboardingDocumentEditor";
import { ageOnDate } from "../../lib/onboarding-age";

type PortalDocument = { id: string; document_key: string; status: string; current_revision: number; signature_url?: string | null };
type PortalData = { case_title: string; case_kind: string; participant: { name: string; role: string; status: string }; documents: PortalDocument[] };
type InviteLink = { role: string; name: string; email: string; portal_url: string };

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
  const [teammateName, setTeammateName] = useState("");
  const [teammateEmail, setTeammateEmail] = useState("");
  const [teammateDob, setTeammateDob] = useState("");
  const [guardianName, setGuardianName] = useState("");
  const [guardianEmail, setGuardianEmail] = useState("");
  const [inviteLinks, setInviteLinks] = useState<InviteLink[]>([]);
  const [inviting, setInviting] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch(`/api/onboarding/public/${token}`, { cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "This onboarding link is invalid or expired.");
    setPortal(body as PortalData);
  }, [token]);

  useEffect(() => { load().catch((reason: Error) => setError(reason.message)); }, [load]);

  const teammateAge = ageOnDate(teammateDob);
  const teammateIsMinor = teammateAge !== null && teammateAge < 18;
  const teammateIsTooYoung = teammateAge !== null && teammateAge < 13;

  const inviteTeammate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setInviteLinks([]);
    setInviting(true);
    try {
      const response = await fetch(`/api/onboarding/public/${token}/teammates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: teammateName,
          email: teammateEmail,
          date_of_birth: teammateDob,
          parent: teammateIsMinor ? { name: guardianName, email: guardianEmail } : undefined,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Could not invite the teammate.");
      setInviteLinks(body.invitees ?? []);
      setTeammateName("");
      setTeammateEmail("");
      setTeammateDob("");
      setGuardianName("");
      setGuardianEmail("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not invite the teammate.");
    } finally {
      setInviting(false);
    }
  };

  if (error && !portal) return <main className="mx-auto max-w-3xl p-6 sm:p-10"><div role="alert" className="border-2 border-red-800 bg-red-50 p-5 text-sm text-red-950">{error}</div></main>;
  if (!portal) return <main className="mx-auto max-w-3xl p-8 font-mono text-sm" role="status">Loading your onboarding workspace…</main>;
  if (selectedDocumentId) return <main className="min-h-screen bg-[#f7f4ef] px-4 py-6 text-[#120f0a] sm:py-10"><div className="mx-auto max-w-5xl"><OnboardingDocumentEditor token={token} documentId={selectedDocumentId} onBack={() => setSelectedDocumentId(null)} onChanged={() => void load()} /></div></main>;

  const completed = portal.documents.filter((document) => document.status === "completed").length;
  const leadPacketSubmitted = portal.documents.length > 0 && portal.documents.every((document) => !["awaiting_completion", "draft", "changes_requested"].includes(document.status));
  const canInviteTeammates = portal.case_kind === "fork" && portal.participant.role === "participant" && leadPacketSubmitted;
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
      {canInviteTeammates ? <section aria-labelledby="teammates-heading" className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a] sm:p-6">
        <p className="font-mono text-xs font-bold uppercase tracking-widest text-[#97192c]">Fork team</p>
        <h2 id="teammates-heading" className="text-2xl font-black uppercase">Invite a teammate</h2>
        <p className="mt-2 text-sm text-zinc-600">Each teammate receives their own volunteer packet. Teammates under 18 also get a separate guardian consent workspace.</p>
        <form onSubmit={inviteTeammate} className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 font-mono text-xs font-bold"><span>Teammate full name</span><input required value={teammateName} onChange={(event) => setTeammateName(event.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm font-normal" /></label>
          <label className="space-y-1 font-mono text-xs font-bold"><span>Teammate email</span><input required type="email" value={teammateEmail} onChange={(event) => setTeammateEmail(event.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm font-normal" /></label>
          <label className="space-y-1 font-mono text-xs font-bold"><span>Date of birth</span><input required type="date" value={teammateDob} onChange={(event) => setTeammateDob(event.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm font-normal" /></label>
          {teammateIsMinor ? <fieldset className="space-y-3 border-2 border-black bg-[#fff4dd] p-4 sm:col-span-2">
            <legend className="px-2 font-mono text-xs font-black uppercase">Parent or legal guardian</legend>
            <label className="block space-y-1 font-mono text-xs font-bold"><span>Guardian full name</span><input required value={guardianName} onChange={(event) => setGuardianName(event.target.value)} className="w-full border-2 border-black bg-white px-3 py-2 font-mono text-sm font-normal" /></label>
            <label className="block space-y-1 font-mono text-xs font-bold"><span>Guardian email</span><input required type="email" value={guardianEmail} onChange={(event) => setGuardianEmail(event.target.value)} className="w-full border-2 border-black bg-white px-3 py-2 font-mono text-sm font-normal" /></label>
          </fieldset> : null}
          {teammateIsTooYoung ? <p role="alert" className="border-2 border-red-700 bg-red-50 p-3 font-mono text-xs font-bold text-red-800 sm:col-span-2">Participants must be at least 13 years old for this onboarding workflow.</p> : null}
          <button disabled={inviting || teammateIsTooYoung} className="border-2 border-black bg-[#fc920d] px-4 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a] disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:shadow-none sm:col-span-2">{inviting ? "Creating invitations…" : "Create and send invitations"}</button>
        </form>
        {inviteLinks.length ? <div role="status" className="mt-5 border-2 border-emerald-800 bg-emerald-50 p-4 text-sm text-emerald-950"><p className="font-bold">Invitations created.</p><p className="mt-1">If email delivery is unavailable, share these links with only the named recipient:</p><ul className="mt-3 space-y-2">{inviteLinks.map((invitee) => <li key={`${invitee.role}-${invitee.email}`}><strong>{invitee.name} ({invitee.role})</strong>: <Link className="break-all underline" href={invitee.portal_url}>{invitee.portal_url}</Link></li>)}</ul></div> : null}
      </section> : null}
      <aside className="border-2 border-black bg-white p-5 text-sm leading-6"><h2 className="font-black uppercase">How review works</h2><ol className="mt-3 grid gap-3 sm:grid-cols-3"><li><strong>1. Fill and submit.</strong><br />HQ receives a frozen revision.</li><li><strong>2. Address comments.</strong><br />Requested changes reopen only the relevant document.</li><li><strong>3. HQ finalizes.</strong><br />PDF compilation happens only after approval and signing.</li></ol></aside>
    </div>
  </main>;
}
