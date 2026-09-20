"use client";

import { Badge, Input, Skeleton } from "@bnb/ui";
import { AlertCircle, Search, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getMembers } from "lib/users";

interface MemberRole {
  slug: string;
  name: string;
}

interface Member {
  id: string;
  display_name: string;
  email?: string | null;
  title?: string | null;
  avatar_url?: string | null;
  discord_id: string;
  discord_username: string;
  roles: MemberRole[];
  created_at: string;
}

export function MembersContent() {
  const [users, setUsers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers((await getMembers()) as Member[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load members.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadUsers(); }, []);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return users;
    return users.filter((user) =>
      [
        user.display_name,
        user.discord_username,
        user.email,
        ...user.roles.map((role) => role.name),
      ].some((value) => value?.toLowerCase().includes(query)),
    );
  }, [search, users]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-2 border-[#5b0f1a] bg-[#3c0a12] p-5 text-white shadow-[4px_4px_0_#120f0a] sm:flex-row sm:items-end sm:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#fc920d]">People network</p><h2 className="mt-1 font-heading text-2xl font-bold">Know who is in the room.</h2><p className="mt-2 max-w-xl text-sm text-white/70">Active members, Discord-linked identities, and elevated access in one reviewable list.</p></div>
        <div className="flex items-center gap-2 text-sm text-white/75"><Users className="size-4" aria-hidden="true" />{loading ? "Loading" : `${users.length} signed-in members`}</div>
      </div>

      <label className="relative block max-w-md"><span className="sr-only">Search members</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /><Input placeholder="Search name, Discord, email, or role" value={search} onChange={(event) => setSearch(event.target.value)} className="pl-10" /></label>

      {error ? <div role="alert" className="flex items-center justify-between gap-4 border-2 border-red-700 bg-red-50 p-4 text-sm text-red-900"><span className="flex items-center gap-2"><AlertCircle className="size-4" aria-hidden="true" />{error}</span><button type="button" onClick={() => void loadUsers()} className="font-bold underline">Try again</button></div> : null}

      <div className="overflow-x-auto border-2 border-border bg-background shadow-shadow"><table className="w-full min-w-[760px] text-sm"><caption className="sr-only">Discord-linked Motherboard members</caption><thead className="bg-[#120f0a] text-left text-xs uppercase tracking-wide text-white"><tr><th className="px-4 py-3">Member</th><th className="px-4 py-3">Discord</th><th className="px-4 py-3">Profile email</th><th className="px-4 py-3">Roles</th><th className="px-4 py-3">Joined</th></tr></thead><tbody>
        {loading ? Array.from({ length: 4 }, (_, index) => <tr key={index} className="border-b border-border"><td colSpan={5} className="p-4"><Skeleton className="h-5 w-full" /></td></tr>) : null}
        {!loading && filteredUsers.length === 0 ? <tr><td colSpan={5} className="p-10 text-center text-muted-foreground">{search ? `No members match “${search}”.` : "No Discord-linked members have signed in yet."}</td></tr> : null}
        {!loading ? filteredUsers.map((user) => { const name = user.display_name.trim() || user.discord_username; return <tr key={user.id} className="border-b border-border last:border-0 hover:bg-[#97192c]/5"><td className="px-4 py-3"><div className="flex items-center gap-3">{user.avatar_url ? <img src={user.avatar_url} alt="" className="size-8 border-2 border-border object-cover" /> : <div className="flex size-8 items-center justify-center border-2 border-border bg-[#f3e5d4] text-xs font-bold" aria-hidden="true">{name.charAt(0).toUpperCase()}</div>}<div><div className="font-semibold">{name}</div>{user.title ? <div className="text-xs text-muted-foreground">{user.title}</div> : null}</div></div></td><td className="px-4 py-3"><div className="font-medium">@{user.discord_username}</div><div className="text-xs text-muted-foreground">{user.discord_id}</div></td><td className="px-4 py-3 text-muted-foreground">{user.email || "—"}</td><td className="px-4 py-3"><div className="flex flex-wrap gap-1">{user.roles.length ? user.roles.map((role) => <Badge key={role.slug} variant="neutral">{role.name}</Badge>) : <span className="text-muted-foreground">No synced roles</span>}</div></td><td className="px-4 py-3 text-muted-foreground">{new Date(user.created_at).toLocaleDateString()}</td></tr>; }) : null}
      </tbody></table></div>
    </div>
  );
}
