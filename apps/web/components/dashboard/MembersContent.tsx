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
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />

        <Input
          placeholder="Search members..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-[#111] text-white placeholder:text-white/50"
        />
      </div>

      {/* Table placeholder */}
      <div className="rounded-base border-2 border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-[#111]">
              <th className="px-4 py-3 text-left">Member</th>
              <th className="px-4 py-3 text-left">Email</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Role</th>
              <th className="px-4 py-3 text-left">Joined</th>
            </tr>
          </thead>

          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="p-6 text-center">
                  Loading...
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id} className="border-b border-border">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-full bg-[#222] flex items-center justify-center text-xs font-bold">
                        {user.display_name?.charAt(0)}
                      </div>

                      <span>{user.display_name}</span>
                    </div>
                  </td>

                  <td className="px-4 py-3">{user.email}</td>

                  <td className="px-4 py-3">
                    <Badge variant={user.is_active ? "success" : "danger"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>

                  <td className="px-4 py-3">
                    <Badge
                      variant={user.is_super_admin ? "warning" : "neutral"}
                    >
                      {user.is_super_admin ? "Super Admin" : "Member"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
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
