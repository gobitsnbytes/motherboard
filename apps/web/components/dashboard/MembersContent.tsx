"use client";

import { Badge, Input } from "@bnb/ui";
import { getUsers } from "lib/users";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";

export function MembersContent() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);
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
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-zinc-500" />
        <Input
          placeholder="Search registered members by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-black border-2 border-border text-white placeholder:text-zinc-500 font-mono text-xs shadow-light focus:outline-none focus:border-orange"
        />
      </div>

      {/* Table container */}
      <div className="rounded-base border-2 border-border bg-[#141418] shadow-dark overflow-hidden">
        <table className="w-full text-left text-xs font-mono">
          <thead>
            <tr className="border-b-2 border-border bg-[#121216] text-zinc-400 uppercase text-[11px] font-bold">
              <th className="px-4 py-3">Member</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Joined</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-zinc-400 font-mono">
                  Loading members directory...
                </td>
              </tr>
            ) : filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-zinc-400 font-mono">
                  No members matched your search.
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id} className="hover:bg-[#181820] transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-base border border-border bg-black flex items-center justify-center text-xs font-bold text-white shadow-light">
                        {user.display_name?.charAt(0) || "?"}
                      </div>

                      <span className="font-bold text-white">{user.display_name}</span>
                    </div>
                  </td>

                  <td className="px-4 py-3 text-zinc-300">{user.email || "-"}</td>

                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-base text-[10px] font-bold border ${user.is_active ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-red-950 text-red-400 border-red-800"}`}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>

                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-base text-[10px] font-bold border ${user.is_super_admin ? "bg-orange text-black border-black shadow-light" : "bg-[#181820] text-zinc-300 border-border"}`}>
                      {user.is_super_admin ? "Super Admin" : "Member"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">
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

