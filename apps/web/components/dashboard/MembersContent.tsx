"use client";

import { Badge, Input, Skeleton } from "@bnb/ui";
import { AlertCircle, Search, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getUsers } from "lib/users";

interface Member {
  id: string;
  display_name?: string | null;
  email?: string | null;
  is_active: boolean;
  is_super_admin: boolean;
  created_at: string;
}

interface Member {
  id: string;
  display_name?: string | null;
  email?: string | null;
  is_active: boolean;
  is_super_admin: boolean;
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
      setUsers((await getUsers()) as Member[]);
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
    return users.filter((user) => [user.display_name, user.email].some((value) => value?.toLowerCase().includes(query)));
  }, [search, users]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-2 border-[#5b0f1a] bg-[#3c0a12] p-5 text-white shadow-[4px_4px_0_#120f0a] sm:flex-row sm:items-end sm:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#fc920d]">People network</p><h2 className="mt-1 font-heading text-2xl font-bold">Know who is in the room.</h2><p className="mt-2 max-w-xl text-sm text-white/70">Active members, Discord-linked identities, and elevated access in one reviewable list.</p></div>
        <div className="flex items-center gap-2 text-sm text-white/75"><Users className="size-4" aria-hidden="true" />{loading ? "Loading" : `${users.length} members`}</div>
      </div>

      <label className="relative block max-w-md"><span className="sr-only">Search members</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /><Input placeholder="Search name or email" value={search} onChange={(event) => setSearch(event.target.value)} className="pl-10" /></label>

      {error ? <div role="alert" className="flex items-center justify-between gap-4 border-2 border-red-700 bg-red-50 p-4 text-sm text-red-900"><span className="flex items-center gap-2"><AlertCircle className="size-4" aria-hidden="true" />{error}</span><button type="button" onClick={() => void loadUsers()} className="font-bold underline">Try again</button></div> : null}

      <div className="overflow-hidden border-2 border-border bg-background shadow-shadow"><table className="w-full text-sm"><caption className="sr-only">Motherboard members and account status</caption><thead className="bg-[#120f0a] text-left text-xs uppercase tracking-wide text-white"><tr><th className="px-4 py-3">Member</th><th className="px-4 py-3">Email</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Access</th><th className="px-4 py-3">Joined</th></tr></thead><tbody>
        {loading ? Array.from({ length: 4 }, (_, index) => <tr key={index} className="border-b border-border"><td colSpan={5} className="p-4"><Skeleton className="h-5 w-full" /></td></tr>) : null}
        {!loading && filteredUsers.length === 0 ? <tr><td colSpan={5} className="p-10 text-center text-muted-foreground">{search ? `No members match “${search}”.` : "No members have joined yet."}</td></tr> : null}
        {!loading ? filteredUsers.map((user) => { const name = user.display_name?.trim() || "Unnamed member"; return <tr key={user.id} className="border-b border-border last:border-0 hover:bg-[#97192c]/5"><td className="px-4 py-3"><div className="flex items-center gap-3"><div className="flex size-8 items-center justify-center border-2 border-border bg-[#f3e5d4] text-xs font-bold" aria-hidden="true">{name.charAt(0).toUpperCase()}</div><span className="font-semibold">{name}</span></div></td><td className="px-4 py-3 text-muted-foreground">{user.email || "—"}</td><td className="px-4 py-3"><Badge variant={user.is_active ? "success" : "danger"}>{user.is_active ? "Active" : "Inactive"}</Badge></td><td className="px-4 py-3"><Badge variant={user.is_super_admin ? "warning" : "neutral"}>{user.is_super_admin ? "Super Admin" : "Member"}</Badge></td><td className="px-4 py-3 text-muted-foreground">{new Date(user.created_at).toLocaleDateString()}</td></tr>; }) : null}
      </tbody></table></div>
    </div>
  );
}
