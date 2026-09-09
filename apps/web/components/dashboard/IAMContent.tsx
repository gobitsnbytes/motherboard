"use client";

import { Card, CardContent, CardHeader, CardTitle, Input, Skeleton } from "@bnb/ui";
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

import { AlertCircle, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export function IAMContent() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [groups, setGroups] = useState<IamGroup[]>([]);
  const [permissions, setPermissions] = useState<IamPermission[]>([]);
  const [mappings, setMappings] = useState<IamDiscordMapping[]>([]);
  const filteredGroups = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return groups;
    return groups.filter((group) => `${group.name} ${group.slug} ${group.description ?? ""}`.toLowerCase().includes(query));
  }, [groups, search]);
  const loadIAM = async () => {
    setLoading(true);
    setError(null);
    try {
        const [groupsData, permissionsData, mappingsData] = await Promise.all([
          getGroups(),
          getPermissions(),
          getDiscordMappings(),
        ]);

        setGroups(groupsData);
        setPermissions(permissionsData);
        setMappings(mappingsData);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load IAM data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadIAM(); }, []);
  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="pb-2">
            <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-muted-foreground">
              IAM Groups
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-heading font-black text-foreground">
              {loading ? "..." : groups.length}
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="pb-2">
            <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-muted-foreground">
              Core Permissions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-heading font-black text-foreground">
              {loading ? "..." : permissions.length}
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="pb-2">
            <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-muted-foreground">
              Discord Mappings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-heading font-black text-foreground">
              {loading ? "..." : mappings.length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder="Search groups..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-secondary-background border-2 border-border text-foreground placeholder:text-muted-foreground font-mono text-xs shadow-light focus:outline-none focus:border-orange"
        />
      </div>

      {error ? (
        <div role="alert" className="flex items-center justify-between gap-4 border-2 border-red-700 bg-red-50 p-4 text-sm text-red-900">
          <span className="flex items-center gap-2"><AlertCircle className="size-4" aria-hidden="true" />{error}</span>
          <button type="button" onClick={() => void loadIAM()} className="font-bold text-orange underline">Try again</button>
        </div>
      ) : null}

      {/* Table Placeholder */}
      <Card className="border-2 border-border bg-secondary-background shadow-dark rounded-base overflow-hidden">
        <CardHeader className="border-b-2 border-border bg-muted py-3.5">
          <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-foreground">
            Configured IAM Groups
          </CardTitle>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <caption className="sr-only">Configured Motherboard IAM groups</caption>
              <thead className="border-b-2 border-border bg-muted text-muted-foreground uppercase text-[11px] font-bold">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Slug</th>
                  <th className="px-4 py-3">Description</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr>
                    <td colSpan={3} className="p-6 text-center text-muted-foreground">
                      <Skeleton className="mx-auto h-5 w-3/4" />
                    </td>
                  </tr>
                ) : filteredGroups.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="p-6 text-center text-muted-foreground">
                      {search ? `No IAM groups match “${search}”.` : "No IAM groups found."}
                    </td>
                  </tr>
                ) : (
                  filteredGroups.map((group) => (
                    <tr key={group.id} className="hover:bg-muted/60 transition-colors">
                      <td className="px-4 py-3 font-bold text-foreground">{group.name}</td>
                      <td className="px-4 py-3 text-orange font-bold">{group.slug}</td>
                      <td className="px-4 py-3 text-muted-foreground">{group.description || "-"}</td>
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
