"use client";

import { Input, Skeleton } from "@bnb/ui";
import { getUsers } from "lib/users";
import { AlertCircle, Search } from "lucide-react";
import { useEffect, useState } from "react";

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
  const filteredUsers = users.filter(
  (user) =>
    user.display_name
      ?.toLowerCase()
      .includes(search.toLowerCase()) ||
    user.email
      ?.toLowerCase()
      .includes(search.toLowerCase())
);
  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder="Search registered members by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-12 border-2 border-border bg-white pl-10 font-base text-sm text-foreground placeholder:text-stone-500 shadow-none focus:border-main"
        />
      </div>

      {error ? (
        <div role="alert" className="flex items-center justify-between gap-4 border-2 border-red-700 bg-red-50 p-4 text-sm text-red-900">
          <span className="flex items-center gap-2"><AlertCircle className="size-4" aria-hidden="true" />{error}</span>
          <button type="button" onClick={() => void loadUsers()} className="font-bold underline">Try again</button>
        </div>
      ) : null}

      {/* Table container */}
      <div className="overflow-x-auto border-2 border-border bg-white">
        <table className="w-full text-left text-xs font-mono">
          <thead>
            <tr className="border-b-2 border-border bg-[#f4f1eb] text-stone-600 text-xs font-semibold">
              <th className="px-4 py-3">Member</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Joined</th>
            </tr>
          </thead>

          <caption className="sr-only">Motherboard members and account status</caption>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={5} className="p-4">
                  <Skeleton className="h-6 w-full" />
                </td>
              </tr>
            ) : filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-stone-600">
                  No members matched your search.
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id} className="transition-colors hover:bg-[#f4f1eb]">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex size-8 items-center justify-center border border-border bg-main text-xs font-bold text-main-foreground">
                        {user.display_name?.charAt(0) || "?"}
                      </div>

                      <span className="font-semibold text-foreground">{user.display_name}</span>
                    </div>
                  </td>

                  <td className="px-4 py-3 text-stone-700">{user.email || "-"}</td>

                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-base text-[10px] font-bold border ${user.is_active ? "bg-emerald-50 text-emerald-900 border-emerald-700" : "bg-red-50 text-red-900 border-red-700"}`}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>

                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold border ${user.is_super_admin ? "bg-orange text-black border-black shadow-light" : "bg-stone-100 text-stone-700 border-stone-400"}`}>
                      {user.is_super_admin ? "Super Admin" : "Member"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-stone-600">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
