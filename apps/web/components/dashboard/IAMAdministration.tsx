"use client";

import { useEffect, useState } from "react";
import { Button } from "@bnb/ui";
import { type EffectiveAccess, hasAccess } from "../../lib/access";
import { useAccess } from "./AccessProvider";

type Group = { id: string; name: string };
type Person = { id: string; display_name: string };
type Fork = { id: string; slug: string; city_name: string };
type Entry = { permission_key: string; resource_scope: string | null; expires_at: string | null };
type Policy = { revision: string; grants: Entry[] };
type Member = { user_id: string; source: string; expires_at: string | null };
const inputClass = "min-h-11 w-full border-2 border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-burgundy";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
const json = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export default function IAMAdministration() {
  const { access, refresh } = useAccess();
  const [groups, setGroups] = useState<Group[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [forks, setForks] = useState<Fork[]>([]);
  const [permissions, setPermissions] = useState<Array<{ key: string }>>([]);
  const [groupId, setGroupId] = useState("");
  const [personId, setPersonId] = useState("");
  const [forkId, setForkId] = useState("");
  const [grantKey, setGrantKey] = useState("");
  const [grantScope, setGrantScope] = useState("");
  const [localRole, setLocalRole] = useState("fork_lead");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [inspected, setInspected] = useState<EffectiveAccess | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const canRead = hasAccess(access, "iam.grants.read");
  const canWrite = hasAccess(access, "iam.grants.write");

  useEffect(() => {
    if (!access) return;
    let live = true;
    Promise.all([
      hasAccess(access, "iam.groups.read") ? request<Group[]>("/api/iam/groups") : [],
      hasAccess(access, "iam.users.read") ? request<Person[]>("/api/users") : [],
      hasAccess(access, "iam.permissions.read") ? request<Array<{ key: string }>>("/api/iam/permissions") : [],
      hasAccess(access, "forks.read") ? request<Fork[]>("/api/forks") : [],
    ]).then(([gs, ps, perms, fs]) => {
      if (live) { setGroups(gs); setPeople(ps); setPermissions(perms); setForks(fs); }
    }).catch((error) => { if (live) setNotice(error.message); });
    return () => { live = false; };
  }, [access]);

  useEffect(() => {
    setPolicy(null); setEntries([]); setMembers([]); setReviewing(false);
    if (!groupId) return;
    let live = true;
    Promise.all([
      canRead ? request<Policy>(`/api/iam/groups/${groupId}/policy`) : null,
      request<Member[]>(`/api/iam/groups/${groupId}/members`),
    ]).then(([p, ms]) => {
      if (live) { setPolicy(p); setEntries(p?.grants ?? []); setMembers(ms); }
    }).catch((error) => { if (live) setNotice(error.message); });
    return () => { live = false; };
  }, [groupId, canRead]);

  useEffect(() => {
    setInspected(null);
    if (!personId || !canRead) return;
    let live = true;
    request<EffectiveAccess>(`/api/iam/users/${personId}/access`).then((result) => { if (live) setInspected(result); })
      .catch((error) => { if (live) setNotice(error.message); });
    return () => { live = false; };
  }, [personId, canRead]);

  async function act(work: () => Promise<unknown>, success: string) {
    setBusy(true); setNotice(null);
    try {
      await work(); setNotice(success); await refresh();
      if (personId && canRead) setInspected(await request(`/api/iam/users/${personId}/access`));
      if (groupId) {
        setMembers(await request(`/api/iam/groups/${groupId}/members`));
        if (canRead) { const p = await request<Policy>(`/api/iam/groups/${groupId}/policy`); setPolicy(p); setEntries(p.grants); }
      }
      setReviewing(false);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Change failed."); }
    finally { setBusy(false); }
  }

  if (!access || (!canRead && !hasAccess(access, "iam.groups.read"))) return null;
  return <section className="space-y-6" aria-label="IAM administration">
    <div className="border-t-2 border-border pt-6">
      <h2 className="font-heading text-xl font-bold">Policies and assignments</h2>
      <p className="mt-2 text-sm text-muted-foreground">Every change is explicit and audited. Restarting the app does not restore defaults.</p>
      {notice && <p className="mt-3 border-2 border-border p-3 text-sm" role="status">{notice}</p>}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm font-semibold">Group
          <select className={inputClass} value={groupId} onChange={(e) => setGroupId(e.target.value)} disabled={busy}>
            <option value="">Choose a group</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
        <label className="space-y-2 text-sm font-semibold">Person
          <select className={inputClass} value={personId} onChange={(e) => setPersonId(e.target.value)} disabled={busy}>
            <option value="">Choose a person</option>{people.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
          </select>
        </label>
      </div>
    </div>

    {groupId && policy && <div className="space-y-4 border-2 border-border p-4">
      <h3 className="font-heading font-bold">Group policy</h3>
      {entries.length === 0 && <p className="text-sm">This group has no grants. Membership alone gives no permission.</p>}
      {entries.map((entry, index) => <div key={index} className="grid gap-3 border-b border-border pb-3 md:grid-cols-[1fr_1fr_auto]">
        <label className="space-y-1 text-sm">Permission
          <select className={inputClass} value={entry.permission_key} disabled={!canWrite || busy} onChange={(e) => { setReviewing(false); setEntries(entries.map((row, i) => i === index ? { ...row, permission_key: e.target.value } : row)); }}>
            <option value="">Choose a permission</option>{permissions.map((p) => <option key={p.key}>{p.key}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-sm">Scope
          <select className={inputClass} value={entry.resource_scope ?? ""} disabled={!canWrite || busy} onChange={(e) => { setReviewing(false); setEntries(entries.map((row, i) => i === index ? { ...row, resource_scope: e.target.value || null } : row)); }}>
            <option value="">Global</option>{forks.map((f) => <option key={f.id} value={`fork:${f.slug}`}>{f.city_name}</option>)}
          </select>
          <span className="text-xs text-muted-foreground">{entry.expires_at ? `Expires ${new Date(entry.expires_at).toLocaleString()}` : "No expiry"}</span>
        </label>
        {canWrite && <Button variant="neutral" disabled={busy} onClick={() => { setEntries(entries.filter((_, i) => i !== index)); setReviewing(false); }}>Remove</Button>}
      </div>)}
      {canWrite && <div className="flex flex-wrap gap-3">
        <Button variant="neutral" disabled={busy} onClick={() => { setEntries([...entries, { permission_key: "", resource_scope: null, expires_at: null }]); setReviewing(false); }}>Add permission</Button>
        <Button disabled={busy || entries.some((e) => !e.permission_key)} onClick={() => setReviewing(true)}>Review changes</Button>
      </div>}
      {reviewing && <div className="space-y-3 border-2 border-burgundy p-4">
        <p className="text-sm font-semibold">Replace {policy.grants.length} existing grants with these {entries.length} grants:</p>
        <ul className="space-y-1 font-mono text-xs">{entries.map((e, i) => <li key={i}>{e.permission_key} / {e.resource_scope ?? "global"}</li>)}</ul>
        <p className="text-sm">Removed permissions will stop working immediately. This change applies to everyone in this group.</p>
        <Button disabled={busy} onClick={() => void act(() => request(`/api/iam/groups/${groupId}/policy`, json("PUT", { expected_revision: policy.revision, grants: entries.map(({ permission_key, resource_scope, expires_at }) => ({ permission_key, resource_scope, expires_at })) })), "Policy saved with an audit record.")}>{busy ? "Saving..." : "Apply reviewed policy"}</Button>
      </div>}
    </div>}

    {groupId && <div className="space-y-3 border-2 border-border p-4">
      <h3 className="font-heading font-bold">Group memberships</h3>
      {members.map((m) => <div key={m.user_id} className="flex flex-wrap items-center justify-between gap-3 border-b border-border py-2 text-sm">
        <span>{people.find((p) => p.id === m.user_id)?.display_name ?? m.user_id} <span className="text-muted-foreground">({m.source})</span></span>
        {hasAccess(access, "iam.groups.write") && m.source === "manual" && <Button variant="neutral" disabled={busy} onClick={() => void act(() => request(`/api/iam/groups/${groupId}/members/${m.user_id}`, { method: "DELETE" }), "Manual membership removed.")}>Remove membership</Button>}
      </div>)}
      {hasAccess(access, "iam.groups.write") && <Button disabled={busy || !personId} onClick={() => void act(() => request(`/api/iam/groups/${groupId}/members`, json("POST", { user_id: personId })), "Manual membership recorded.")}>Add selected person</Button>}
    </div>}

    {inspected && <div className="space-y-3 border-2 border-border p-4">
      <h3 className="font-heading font-bold">Selected person's effective access</h3>
      <p className="text-sm">{inspected.groups.map((g) => g.name).join(", ") || "No active group memberships"}</p>
      {inspected.grants.length === 0 && <p className="text-sm">No active grants. Protected operations are denied.</p>}
      {inspected.grants.map((g) => <div key={g.id} className="flex flex-wrap justify-between gap-3 border-b border-border py-2 text-sm">
        <span><strong className="font-mono">{g.permission_key}</strong> / {g.resource_scope ?? "global"}<br />From {g.principal_type === "user" ? "direct grant" : inspected.groups.find((group) => group.id === g.principal_id)?.name ?? g.principal_id}</span>
        {canWrite && g.principal_type === "user" && <Button variant="neutral" disabled={busy} onClick={() => void act(() => request(`/api/iam/grants/${g.id}`, { method: "DELETE" }), "Direct grant revoked.")}>Revoke direct grant</Button>}
      </div>)}
      {canWrite && <div className="grid items-end gap-3 md:grid-cols-3">
        <label className="space-y-1 text-sm">Direct permission<select className={inputClass} value={grantKey} onChange={(e) => setGrantKey(e.target.value)}><option value="">Choose a permission</option>{permissions.map((p) => <option key={p.key}>{p.key}</option>)}</select></label>
        <label className="space-y-1 text-sm">Scope<select className={inputClass} value={grantScope} onChange={(e) => setGrantScope(e.target.value)}><option value="">Global</option>{forks.map((f) => <option key={f.id} value={`fork:${f.slug}`}>{f.city_name}</option>)}</select></label>
        <Button disabled={busy || !grantKey} onClick={() => void act(() => request("/api/iam/grants", json("POST", { principal_type: "user", principal_id: personId, permission_key: grantKey, resource_scope: grantScope || null })), "Direct permission recorded with an audit entry.")}>Grant selected permission</Button>
      </div>}
      <h4 className="font-semibold">Fork assignments</h4>
      <p className="text-sm">{inspected.fork_assignments.map((f) => `${f.city_name}: ${f.local_role}`).join(", ") || "No active fork assignment"}</p>
      {hasAccess(access, "forks.members.write") && <div className="grid items-end gap-3 md:grid-cols-3">
        <label className="space-y-1 text-sm">Fork<select className={inputClass} value={forkId} onChange={(e) => setForkId(e.target.value)}><option value="">Choose a fork</option>{forks.map((f) => <option key={f.id} value={f.id}>{f.city_name}</option>)}</select></label>
        <label className="space-y-1 text-sm">Local role<select className={inputClass} value={localRole} onChange={(e) => setLocalRole(e.target.value)}>{["fork_lead", "track_lead", "contributor", "community"].map((role) => <option key={role}>{role}</option>)}</select></label>
        <Button disabled={busy || !forkId} onClick={() => void act(() => request(`/api/forks/${forkId}/members`, json("POST", { user_id: personId, local_role: localRole })), "Fork assignment recorded. Grant scoped permissions separately in the policy editor.")}>Assign selected person</Button>
      </div>}
    </div>}
  </section>;
}
