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
          className="h-12 border-2 border-border bg-white pl-10 font-base text-sm text-foreground placeholder:text-stone-500 shadow-none focus:border-main"
        />
      </div>

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

          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-stone-600">
                  Loading members directory...
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
                      <div className="flex size-8 items-center justify-center border border-border bg-[#17130f] text-xs font-bold text-white">
                        {user.display_name?.charAt(0) || "?"}
                      </div>

                      <span className="font-semibold text-foreground">{user.display_name}</span>
                    </div>
                  </td>

                  <td className="px-4 py-3 text-stone-700">{user.email || "-"}</td>

                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-base text-[10px] font-bold border ${user.is_active ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-red-950 text-red-400 border-red-800"}`}>
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
