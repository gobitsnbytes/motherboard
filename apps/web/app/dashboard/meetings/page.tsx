"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, CircleAlert, ExternalLink, Link2, Loader2, Plus, RefreshCw, ShieldCheck, Users, Video } from "lucide-react";

type Tab = "bookings" | "pools" | "connections" | "history";
interface Connection { id: string; user_id: string; cal_username: string | null; status: "pending" | "active" | "invalid" | "revoked"; last_verified_at: string | null; last_error_code: string | null; }
interface Pool { id: string; name: string; slug: string; description: string | null; algorithm: string; active: boolean; }
interface Member { id: string; calendar_connection_id: string; event_type_id: number; event_type_slug: string | null; priority: number; weight: number; last_assigned_at: string | null; }
interface Booking { uid: string; status: string; start: string; end: string; meeting_url: string | null; host_user_id: string; attendee_name: string; attendee_email: string; }
interface User { id: string; display_name: string; email: string | null; }
interface LegacyMeeting { id: string; title: string; scheduled_time: number; status: string; location_type: string; }

const fieldClass = "w-full rounded-base border-2 border-border bg-secondary-background px-3 py-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-orange focus:ring-2 focus:ring-orange/25 disabled:cursor-not-allowed disabled:opacity-50";
const primaryButton = "inline-flex min-h-10 items-center justify-center gap-2 rounded-base border-2 border-border bg-orange px-4 py-2 text-sm font-black text-black shadow-light transition-[transform,box-shadow] hover:translate-x-px hover:translate-y-px hover:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "inline-flex min-h-10 items-center justify-center gap-2 rounded-base border-2 border-border bg-secondary-background px-4 py-2 text-sm font-bold text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange disabled:cursor-not-allowed disabled:opacity-50";

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

function formatDate(value: string | number) {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function Status({ value }: { value: string }) {
  const healthy = ["active", "accepted", "scheduled", "completed"].includes(value);
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-bold ${healthy ? "border-emerald-700 bg-emerald-100 text-emerald-900" : "border-amber-700 bg-amber-100 text-amber-950"}`}><span className={`size-1.5 rounded-full ${healthy ? "bg-emerald-700" : "bg-amber-700"}`} />{value.replaceAll("_", " ")}</span>;
}

export default function MeetingsPage() {
  const [tab, setTab] = useState<Tab>("bookings");
  const [connections, setConnections] = useState<Connection[]>([]);
  const [pools, setPools] = useState<Pool[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [history, setHistory] = useState<LegacyMeeting[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [members, setMembers] = useState<Record<string, Member[]>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [connectionRows, poolRows, bookingRows, historyRows, currentUser] = await Promise.all([
        api<Connection[]>("/api/calendar/connections"), api<Pool[]>("/api/calendar/routing-pools"),
        api<Booking[]>("/api/calendar/bookings"), api<LegacyMeeting[]>("/api/meetings"), api<User>("/api/users/me"),
      ]);
      setConnections(connectionRows); setPools(poolRows); setBookings(bookingRows); setHistory(historyRows);
      try { setUsers(await api<User[]>("/api/users/")); } catch { setUsers([currentUser]); }
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Could not load calendar operations" });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function loadMembers(poolId: string) {
    const rows = await api<Member[]>(`/api/calendar/routing-pools/${poolId}/members`);
    setMembers((current) => ({ ...current, [poolId]: rows }));
  }

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label); setMessage(null);
    try { await action(); setMessage({ kind: "ok", text: "Saved. Cal.com remains responsible for invitations and calendar updates." }); }
    catch (error) { setMessage({ kind: "error", text: error instanceof Error ? error.message : "Request failed" }); }
    finally { setBusy(null); }
  }

  async function createConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
    await run("connection", async () => {
      await api("/api/calendar/connections/calcom", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ user_id: form.get("user_id"), api_key: form.get("api_key") }) });
      formElement.reset(); await load();
    });
  }

  async function createPool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
    await run("pool", async () => {
      await api("/api/calendar/routing-pools", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: form.get("name"), slug: form.get("slug"), description: form.get("description") || null, algorithm: form.get("algorithm") }) });
      formElement.reset(); await load();
    });
  }

  async function addMember(event: FormEvent<HTMLFormElement>, poolId: string) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
    await run(`member-${poolId}`, async () => {
      await api(`/api/calendar/routing-pools/${poolId}/members`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ calendar_connection_id: form.get("connection_id"), event_type_id: Number(form.get("event_type_id")) }) });
      formElement.reset(); await loadMembers(poolId);
    });
  }

  const userName = (id: string) => users.find((user) => user.id === id)?.display_name ?? id.slice(0, 8);

  return <main className="mx-auto max-w-7xl space-y-6 pb-12">
    <header className="flex flex-col gap-4 border-b-2 border-border pb-5 md:flex-row md:items-end md:justify-between">
      <div><div className="mb-2 flex items-center gap-2 text-sm font-bold text-orange"><ShieldCheck className="size-4" /> Cal.com-owned scheduling</div><h1 className="text-3xl font-black tracking-tight text-foreground">Calendar operations</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Motherboard routes to an available host. Cal.com creates Google Meet and sends every attendee update.</p></div>
      <button className={secondaryButton} onClick={() => void load()} disabled={loading}><RefreshCw className={`size-4 ${loading ? "animate-spin motion-reduce:animate-none" : ""}`} /> Refresh</button>
    </header>

    {message && <div role="status" className={`flex items-start gap-2 rounded-base border-2 p-3 text-sm font-semibold ${message.kind === "ok" ? "border-emerald-700 bg-emerald-100 text-emerald-950" : "border-red-700 bg-red-100 text-red-950"}`}>{message.kind === "ok" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <CircleAlert className="mt-0.5 size-4 shrink-0" />}{message.text}</div>}

    <nav aria-label="Calendar sections" className="flex gap-2 overflow-x-auto pb-1">{([["bookings", "Bookings"], ["pools", "Routing pools"], ["connections", "Host connections"], ["history", "Legacy history"]] as const).map(([value, label]) => <button key={value} onClick={() => setTab(value)} aria-current={tab === value ? "page" : undefined} className={tab === value ? primaryButton : secondaryButton}>{label}</button>)}</nav>

    {loading && <div className="grid gap-3" aria-label="Loading calendar data">{[0, 1, 2].map((key) => <div key={key} className="h-20 animate-pulse rounded-base bg-muted motion-reduce:animate-none" />)}</div>}

    {!loading && tab === "bookings" && <section aria-labelledby="bookings-title">
      <div className="mb-4 flex items-center justify-between gap-3"><div><h2 id="bookings-title" className="text-xl font-black">Cal.com bookings</h2><p className="text-sm text-muted-foreground">Read-only operational view. Changes flow through Cal.com.</p></div><span className="font-mono text-sm text-muted-foreground">{bookings.length} total</span></div>
      {bookings.length === 0 ? <div className="rounded-base border-2 border-dashed border-border p-8 text-center"><CalendarDays className="mx-auto mb-3 size-7 text-orange" /><p className="font-bold">No routed bookings yet.</p><p className="mt-1 text-sm text-muted-foreground">Create a routing pool, add hosts, then share its public link.</p></div> : <div className="overflow-x-auto rounded-base border-2 border-border"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-muted text-xs uppercase text-muted-foreground"><tr><th className="p-3">When</th><th className="p-3">Attendee</th><th className="p-3">Host</th><th className="p-3">Status</th><th className="p-3">Conference</th></tr></thead><tbody>{bookings.map((booking) => <tr key={booking.uid} className="border-t-2 border-border bg-secondary-background"><td className="p-3 font-semibold">{formatDate(booking.start)}</td><td className="p-3"><div className="font-bold">{booking.attendee_name}</div><div className="text-xs text-muted-foreground">{booking.attendee_email}</div></td><td className="p-3">{userName(booking.host_user_id)}</td><td className="p-3"><Status value={booking.status} /></td><td className="p-3">{booking.meeting_url ? <a className="inline-flex items-center gap-1 font-bold text-orange underline underline-offset-4" href={booking.meeting_url} target="_blank" rel="noreferrer">Google Meet <ExternalLink className="size-3.5" /></a> : <span className="text-muted-foreground">Pending</span>}</td></tr>)}</tbody></table></div>}
    </section>}

    {!loading && tab === "connections" && <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]" aria-labelledby="connections-title">
      <div><h2 id="connections-title" className="text-xl font-black">Individual Cal.com accounts</h2><p className="mb-4 mt-1 text-sm text-muted-foreground">Each host connects one account. API keys are encrypted and never shown again.</p><div className="space-y-3">{connections.map((connection) => <div key={connection.id} className="flex flex-col gap-3 rounded-base border-2 border-border bg-secondary-background p-4 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><strong>{userName(connection.user_id)}</strong><Status value={connection.status} /></div><p className="mt-1 truncate text-xs text-muted-foreground">{connection.cal_username ? `cal.com/${connection.cal_username}` : connection.last_error_code ?? "Verification required"}</p></div><div className="flex gap-2">{connection.status !== "revoked" && <button className={secondaryButton} disabled={busy === connection.id} onClick={() => void run(connection.id, async () => { await api(`/api/calendar/connections/${connection.id}/verify`, { method: "POST" }); await load(); })}>{busy === connection.id ? <Loader2 className="size-4 animate-spin motion-reduce:animate-none" /> : <RefreshCw className="size-4" />} Verify</button>}{connection.status !== "revoked" && <button className={secondaryButton} onClick={() => void run(`revoke-${connection.id}`, async () => { await api(`/api/calendar/connections/${connection.id}`, { method: "DELETE" }); await load(); })}>Revoke</button>}</div></div>)}{connections.length === 0 && <p className="rounded-base border-2 border-dashed border-border p-6 text-sm text-muted-foreground">No hosts connected yet.</p>}</div></div>
      <form onSubmit={createConnection} className="h-fit space-y-4 rounded-base border-2 border-border bg-secondary-background p-5"><div><h3 className="font-black">Connect a host</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">Use a dedicated Cal.com API key after Google Calendar and Google Meet are connected.</p></div><label className="block text-sm font-bold">Host<select name="user_id" required className={`${fieldClass} mt-1`}><option value="">Select a host</option>{users.map((user) => <option key={user.id} value={user.id}>{user.display_name}{user.email ? ` — ${user.email}` : ""}</option>)}</select></label><label className="block text-sm font-bold">Cal.com API key<input name="api_key" type="password" required minLength={8} autoComplete="new-password" className={`${fieldClass} mt-1`} placeholder="cal_live_…" /></label><button className={`${primaryButton} w-full`} disabled={busy === "connection"}>{busy === "connection" ? <Loader2 className="size-4 animate-spin motion-reduce:animate-none" /> : <Plus className="size-4" />} Save connection</button></form>
    </section>}

    {!loading && tab === "pools" && <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]" aria-labelledby="pools-title">
      <div><h2 id="pools-title" className="text-xl font-black">Routing pools</h2><p className="mb-4 mt-1 text-sm text-muted-foreground">Combine individual event types behind one booking link.</p><div className="space-y-4">{pools.map((pool) => <article key={pool.id} className="rounded-base border-2 border-border bg-secondary-background"><div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex items-center gap-2"><h3 className="font-black">{pool.name}</h3><Status value={pool.active ? "active" : "inactive"} /></div><p className="mt-1 text-sm text-muted-foreground">{pool.description || "No description"}</p><p className="mt-2 font-mono text-xs text-muted-foreground">{pool.algorithm.replaceAll("_", " ")}</p></div><div className="flex flex-wrap gap-2"><a className={secondaryButton} href={`/book/${pool.slug}`} target="_blank" rel="noreferrer"><Link2 className="size-4" /> Public page</a><button className={secondaryButton} onClick={() => void loadMembers(pool.id)}><Users className="size-4" /> Hosts</button></div></div>{members[pool.id] && <div className="border-t-2 border-border p-4"><div className="mb-3 space-y-2">{(members[pool.id] ?? []).map((member) => <div key={member.id} className="flex items-center justify-between gap-3 text-sm"><span>{userName(connections.find((connection) => connection.id === member.calendar_connection_id)?.user_id ?? "")} · event #{member.event_type_id}</span><span className="font-mono text-xs text-muted-foreground">{member.event_type_slug ?? "verified"}</span></div>)}{(members[pool.id] ?? []).length === 0 && <p className="text-sm text-muted-foreground">No hosts in this pool.</p>}</div><form className="flex flex-col gap-2 sm:flex-row" onSubmit={(event) => addMember(event, pool.id)}><select name="connection_id" required className={fieldClass}><option value="">Active connection</option>{connections.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{userName(item.user_id)}</option>)}</select><input name="event_type_id" type="number" min="1" required className={fieldClass} placeholder="Cal event type ID" /><button className={primaryButton} disabled={busy === `member-${pool.id}`}><Plus className="size-4" /> Add host</button></form></div>}</article>)}{pools.length === 0 && <p className="rounded-base border-2 border-dashed border-border p-6 text-sm text-muted-foreground">No routing pools yet. Connect hosts first, then create one here.</p>}</div></div>
      <form onSubmit={createPool} className="h-fit space-y-4 rounded-base border-2 border-border bg-secondary-background p-5"><div><h3 className="font-black">New routing pool</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">Round robin is the safest default for shared scheduling.</p></div><label className="block text-sm font-bold">Name<input name="name" required maxLength={120} className={`${fieldClass} mt-1`} placeholder="Community onboarding" /></label><label className="block text-sm font-bold">Public slug<input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" className={`${fieldClass} mt-1`} placeholder="community-onboarding" /></label><label className="block text-sm font-bold">Description<textarea name="description" rows={3} className={`${fieldClass} mt-1 resize-y`} placeholder="Who this booking route is for" /></label><label className="block text-sm font-bold">Routing<select name="algorithm" className={`${fieldClass} mt-1`}><option value="round_robin">Round robin</option><option value="weighted_round_robin">Weighted round robin</option><option value="priority">Priority</option></select></label><button className={`${primaryButton} w-full`} disabled={busy === "pool"}><Plus className="size-4" /> Create pool</button></form>
    </section>}

    {!loading && tab === "history" && <section aria-labelledby="history-title"><div className="mb-4"><h2 id="history-title" className="text-xl font-black">Legacy meeting history</h2><p className="mt-1 text-sm text-muted-foreground">Discord-era records are preserved for reference. They cannot create, reschedule, or email meetings.</p></div><div className="space-y-2">{history.map((meeting) => <div key={meeting.id} className="flex flex-col gap-2 rounded-base border-2 border-border bg-secondary-background p-4 sm:flex-row sm:items-center sm:justify-between"><div><strong>{meeting.title}</strong><p className="mt-1 text-xs text-muted-foreground">{formatDate(meeting.scheduled_time)} · {meeting.location_type}</p></div><Status value={meeting.status} /></div>)}{history.length === 0 && <p className="rounded-base border-2 border-dashed border-border p-6 text-sm text-muted-foreground">No legacy meetings.</p>}</div></section>}

    <aside className="flex items-start gap-3 rounded-base border-2 border-border bg-muted p-4 text-sm text-foreground"><Video className="mt-0.5 size-5 shrink-0 text-orange" /><div><strong>Google Meet only.</strong> Motherboard does not create Discord channels, send booking email, or attach ICS files. Transcription is unavailable until a separate Google Workspace integration exists.</div></aside>
  </main>;
}
