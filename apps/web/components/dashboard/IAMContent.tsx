"use client";

import { Card, CardContent, CardHeader, CardTitle, Input } from "@bnb/ui";
import { getDiscordMappings, getPermissions, getGroups } from "lib/iam";

interface IamGroup {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  is_system: boolean;
}

interface IamPermission {
  key: string;
  description: string;
}

interface IamDiscordMapping {
  id: string;
  discord_role_id: string;
  discord_role_name: string;
  group_id: string;
  sync_enabled: boolean;
  priority: number;
}

import { Search } from "lucide-react";
import { useEffect, useState } from "react";

export function IAMContent() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const [groups, setGroups] = useState<IamGroup[]>([]);
  const [permissions, setPermissions] = useState<IamPermission[]>([]);
  const [mappings, setMappings] = useState<IamDiscordMapping[]>([]);
  useEffect(() => {
    async function loadIAM() {
      try {
        const [groupsData, permissionsData, mappingsData] = await Promise.all([
          getGroups(),
          getPermissions(),
          getDiscordMappings(),
        ]);

        setGroups(groupsData);
        setPermissions(permissionsData);
        setMappings(mappingsData);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }

    loadIAM();
  }, []);
  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Groups</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {loading ? "..." : groups.length}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Permissions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {loading ? "..." : permissions.length}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Discord Mappings</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {loading ? "..." : mappings.length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />

        <Input
          placeholder="Search groups..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-[#111] text-white placeholder:text-white/50"
        />
      </div>

      {/* Table Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Groups</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-left">Name</th>

                  <th className="px-4 py-3 text-left">Slug</th>

                  <th className="px-4 py-3 text-left">Description</th>
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={3} className="p-4 text-center">
                      Loading...
                    </td>
                  </tr>
                ) : (
                  groups.map((group) => (
                    <tr key={group.id} className="border-b border-border">
                      <td className="px-4 py-3">{group.name}</td>

                      <td className="px-4 py-3">{group.slug}</td>

                      <td className="px-4 py-3">{group.description || "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
