"use client";

import { useEffect, useState } from "react";

type ParticipantRow = { id: string; role: string; name: string; email: string; status: string; portal_url?: string | null; documents: Array<{ id: string; status: string; document_key: string; signature_request_id?: string | null }> };
type CaseRow = { id: string; title: string; kind: string; status: string; documents: Array<{ id: string; status: string; document_key: string }>; participants: ParticipantRow[] };

export default function OnboardingDashboardPage() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [kind, setKind] = useState("volunteer");
  const [title, setTitle] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [dob, setDob] = useState("");
  const [forkName, setForkName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editingParticipantId, setEditingParticipantId] = useState<string | null>(null);
  const [emailDraft, setEmailDraft] = useState("");
  const [savingParticipantId, setSavingParticipantId] = useState<string | null>(null);

  const load = async () => {
    const response = await fetch("/api/onboarding/cases", { cache: "no-store" });
    if (response.ok) setCases(await response.json());
  };
  useEffect(() => { load().catch(() => setError("Could not load onboarding cases.")); }, []);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    const response = await fetch("/api/onboarding/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, title, fork_name: kind === "fork" ? forkName : undefined, participant: { name, email, date_of_birth: dob, is_volunteer: true } }) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { setError(typeof body.detail === "string" ? body.detail : "Could not create case."); return; }
    setTitle(""); setName(""); setEmail(""); setDob(""); setForkName(""); await load();
  };

  const acceptSignedPacket = async (caseId: string) => {
    const response = await fetch(`/api/onboarding/cases/${caseId}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: "accepted" }) });
    if (!response.ok) { const body = await response.json().catch(() => ({})); setError(typeof body.detail === "string" ? body.detail : "Review could not be recorded."); return; }
    await load();
  };

  const updateEmail = async (caseId: string, participantId: string) => {
    setError(null);
    setSavingParticipantId(participantId);
    try {
      const response = await fetch(`/api/onboarding/cases/${caseId}/participants/${participantId}/email`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: emailDraft }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Could not update the email.");
      setEditingParticipantId(null);
      setEmailDraft("");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update the email.");
    } finally {
      setSavingParticipantId(null);
    }
  };

  return <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
    <header className="flex flex-col gap-3 border-2 border-black bg-[#3c0a12] p-6 text-white shadow-[6px_6px_0_#120f0a] sm:flex-row sm:items-end sm:justify-between"><div><p className="font-mono text-xs uppercase tracking-widest text-[#fc920d]">workflow / onboarding</p><h1 className="mt-2 text-3xl font-black uppercase">Digital onboarding</h1><p className="mt-1 text-sm text-white/75">Portal collection, evidence, review, and sealed PDF hand-off.</p></div><span className="font-mono text-xs uppercase text-[#fc920d]">IAM reviewed</span></header>
    {error && <div className="border-2 border-red-700 bg-red-50 p-4 font-mono text-sm text-red-900">{error}</div>}
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <form onSubmit={create} className="space-y-4 border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a]"><h2 className="text-lg font-black uppercase">Start a case</h2><select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm"><option value="volunteer">Volunteer</option><option value="fork">Fork lead</option></select><input required placeholder="Case title" value={title} onChange={(e) => setTitle(e.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm" /><input required placeholder="Person name" value={name} onChange={(e) => setName(e.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm" /><input required type="email" placeholder="Person email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm" /><input required type="date" value={dob} onChange={(e) => setDob(e.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm" />{kind === "fork" && <input required placeholder="Fork name" value={forkName} onChange={(e) => setForkName(e.target.value)} className="w-full border-2 border-black px-3 py-2 font-mono text-sm" />}<button className="w-full border-2 border-black bg-[#fc920d] px-4 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a]">Create and send portal link</button></form>
      <section className="space-y-3"><h2 className="text-lg font-black uppercase">Cases</h2>{cases.length === 0 ? <div className="border-2 border-dashed border-zinc-400 p-8 font-mono text-sm text-zinc-600">No onboarding cases yet.</div> : cases.map((item) => <article key={item.id} className="border-2 border-black bg-white p-5 shadow-[3px_3px_0_#120f0a]"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-black uppercase">{item.title}</h3><p className="font-mono text-xs text-zinc-600">{item.kind} / {item.status}</p></div><div className="flex items-center gap-2"><span className="border-2 border-black bg-[#f7f4ef] px-2 py-1 font-mono text-[10px] uppercase">{item.participants.length} participant(s)</span>{item.status !== "approved" && item.status !== "rejected" && <button type="button" onClick={() => acceptSignedPacket(item.id)} className="border-2 border-black bg-[#fc920d] px-2 py-1 font-mono text-[10px] font-black uppercase">Accept signed docs</button>}</div></div><div className="mt-3 space-y-2">{item.participants.map((person) => { const canEditEmail = person.role === "participant" && person.status === "invited" && person.documents.length > 0 && person.documents.every((document) => document.status === "awaiting_completion" && !document.signature_request_id); const isEditing = editingParticipantId === person.id; return <div key={person.id} className="border-t border-zinc-200 pt-2 text-sm"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><span>{person.name} <span className="font-mono text-xs text-zinc-500">{person.status}</span></span><div className="flex items-center gap-3">{canEditEmail && <button type="button" onClick={() => { setEditingParticipantId(isEditing ? null : person.id); setEmailDraft(person.email); }} className="font-mono text-xs font-bold text-[#97192c] underline">Edit email</button>}{person.portal_url && <a href={person.portal_url} target="_blank" rel="noreferrer" className="font-mono text-xs font-bold text-[#97192c] underline">Copy/open portal</a>}</div></div>{isEditing && <form onSubmit={(event) => { event.preventDefault(); updateEmail(item.id, person.id); }} className="mt-3 flex flex-col gap-2 sm:flex-row"><label className="sr-only" htmlFor={`email-${person.id}`}>Correct email for {person.name}</label><input id={`email-${person.id}`} required type="email" value={emailDraft} onChange={(event) => setEmailDraft(event.target.value)} className="min-w-0 flex-1 border-2 border-black px-3 py-2 font-mono text-sm" /><button disabled={savingParticipantId === person.id} className="border-2 border-black bg-[#fc920d] px-3 py-2 font-mono text-xs font-black uppercase disabled:cursor-not-allowed disabled:opacity-60">{savingParticipantId === person.id ? "Saving…" : "Save email"}</button><button type="button" onClick={() => setEditingParticipantId(null)} className="border-2 border-black px-3 py-2 font-mono text-xs font-black uppercase">Cancel</button></form>}</div>; })}</div><div className="mt-3 border-t border-zinc-200 pt-3 font-mono text-xs text-zinc-600">{item.documents.map((document) => `${document.document_key.replaceAll("_", " ")}: ${document.status}`).join(" / ")}</div></article>)}</section>
    </div>
  </div>;
}
