"use client";

import { Badge, Button, Skeleton } from "@bnb/ui";
import { Search, ShieldCheck, Users, Waypoints } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDiscordMappings, getGroups, getIamMe, getPermissions } from "lib/iam";

interface IamGroup {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  is_system: boolean;
}

interface IamPermission {
  key: string;
  description: string | null;
}

interface IamGrant {
  id: string;
  permission_key: string;
  resource_scope: string | null;
  expires_at: string | null;
}

interface IamMe {
  principal: {
    user_id: string;
    group_ids: string[];
    is_super_admin: boolean;
  };
  grants: IamGrant[];
}

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function formatExpiry(value: string | null) {
  if (!value) return "No expiry";
  return `Until ${new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value))}`;
}

export function IAMContent() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groups, setGroups] = useState<IamGroup[]>([]);
  const [permissions, setPermissions] = useState<IamPermission[]>([]);
  const [mappingCount, setMappingCount] = useState(0);
  const [iamMe, setIamMe] = useState<IamMe | null>(null);

  const loadIam = async () => {
    setLoading(true);
    setError(null);
    try {
      const [groupsData, permissionsData, mappingsData, meData] = await Promise.all([
        getGroups(),
        getPermissions(),
        getDiscordMappings(),
        getIamMe(),
      ]);
      setGroups(groupsData ?? []);
      setPermissions(permissionsData ?? []);
      setMappingCount((mappingsData ?? []).length);
      setIamMe(meData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load access data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadIam();
  }, []);

  const filteredGroups = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return groups;
    return groups.filter((group) =>
      `${group.name} ${group.slug} ${group.description ?? ""}`.toLowerCase().includes(query),
    );
  }, [groups, search]);

  const visibleGrants = iamMe?.grants.slice(0, 8) ?? [];

  return (
    <section className="space-y-6" aria-labelledby="iam-overview-title">
      <div className="flex flex-col gap-4 border-2 border-border bg-[#120f0a] p-5 text-white shadow-shadow md:flex-row md:items-end md:justify-between">
        <div className="max-w-2xl">
          <p className="mb-2 text-xs font-heading font-semibold uppercase tracking-[0.16em] text-[#fc920d]">Control plane</p>
          <h2 id="iam-overview-title" className="font-heading text-2xl font-bold tracking-tight md:text-3xl">Access should be explainable.</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-white/75">Review your effective access, the groups that shape the network, and the Discord mappings that feed provisioning.</p>
        </div>
        <Button type="button" variant="neutral" onClick={() => void loadIam()} disabled={loading}>{loading ? "Refreshing…" : "Refresh access"}</Button>
      </div>

      {error ? (
        <div className="flex flex-col gap-3 border-2 border-red-500 bg-red-950/40 p-4 text-sm text-white" role="alert">
          <p className="font-semibold">Access data could not be loaded.</p>
          <p className="text-white/75">{error}</p>
          <Button type="button" variant="neutral" size="sm" className="w-fit" onClick={() => void loadIam()}>Try again</Button>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3" aria-label="IAM summary">
        {[
          { label: "Groups", value: groups.length, icon: Users },
          { label: "Permission keys", value: permissions.length, icon: ShieldCheck },
          { label: "Discord mappings", value: mappingCount, icon: Waypoints },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="flex items-center gap-3 border-2 border-border bg-secondary-background p-4">
            <span className="flex size-10 items-center justify-center border-2 border-border bg-[#97192c] text-white" aria-hidden="true"><Icon className="size-5" /></span>
            <div><p className="text-xs font-heading uppercase tracking-wide text-muted-foreground">{label}</p><p className="font-heading text-xl font-bold text-foreground">{loading ? "—" : value}</p></div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <div className="border-2 border-border bg-secondary-background p-5">
          <div className="flex flex-col gap-2 border-b-2 border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
            <div><h3 className="font-heading text-lg font-bold text-foreground">Your effective access</h3><p className="mt-1 text-sm text-muted-foreground">Every grant below is current as of this request.</p></div>
            {iamMe?.principal.is_super_admin ? <Badge variant="warning">Break-glass admin</Badge> : null}
          </div>
          {loading ? (
            <div className="space-y-3 pt-4"><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
          ) : !iamMe ? null : (
            <div className="space-y-3 pt-4">
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground"><span>User {shortId(iamMe.principal.user_id)}</span><span aria-hidden="true">·</span><span>{iamMe.principal.group_ids.length} active group memberships</span></div>
              {visibleGrants.length === 0 ? <div className="border-2 border-dashed border-border p-5 text-sm text-muted-foreground">No direct or group grants are attached to this principal.</div> : visibleGrants.map((grant) => (
                <div key={grant.id} className="flex flex-col gap-2 border-2 border-border bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div><p className="font-mono text-sm font-semibold text-foreground">{grant.permission_key}</p><p className="mt-1 text-xs text-muted-foreground">{grant.resource_scope ?? "Global scope"}</p></div>
                  <Badge variant={grant.expires_at ? "warning" : "neutral"}>{formatExpiry(grant.expires_at)}</Badge>
                </div>
              ))}
              {iamMe.grants.length > visibleGrants.length ? <p className="text-xs text-muted-foreground">Showing {visibleGrants.length} of {iamMe.grants.length} grants.</p> : null}
            </div>
          )}
        </div>

        <div className="border-2 border-border bg-[#97192c] p-5 text-white">
          <h3 className="font-heading text-lg font-bold">Scope check</h3>
          <p className="mt-2 text-sm leading-6 text-white/80">City and track access should be explicit. A role mapping can add membership; it cannot quietly become global access.</p>
          <div className="mt-5 space-y-3 text-sm">
            <div className="border-2 border-white/30 bg-black/10 p-3"><strong>Global</strong><br /><span className="text-white/75">HQ and executive permissions only.</span></div>
            <div className="border-2 border-white/30 bg-black/10 p-3"><strong>City fork</strong><br /><span className="text-white/75">A named city, such as <code>fork:delhi</code>.</span></div>
            <div className="border-2 border-white/30 bg-black/10 p-3"><strong>Track</strong><br /><span className="text-white/75">A named track inside a city fork.</span></div>
          </div>
        </div>
      </div>

      <div className="border-2 border-border bg-secondary-background p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div><h3 className="font-heading text-lg font-bold text-foreground">Groups in the network</h3><p className="mt-1 text-sm text-muted-foreground">Search the roles that shape membership and access.</p></div>
          <label className="relative block w-full md:max-w-xs"><span className="sr-only">Search groups</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /><input className="h-10 w-full border-2 border-border bg-background pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-[#97192c]" placeholder="Search groups" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        </div>
        <div className="mt-4 overflow-hidden border-2 border-border">
          {loading ? <div className="space-y-2 p-3"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : filteredGroups.length === 0 ? <p className="p-5 text-sm text-muted-foreground">No groups match “{search}”.</p> : <div className="divide-y-2 divide-border">{filteredGroups.map((group) => <div key={group.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><p className="font-heading font-semibold text-foreground">{group.name}</p>{group.is_system ? <Badge variant="neutral">System</Badge> : null}</div><p className="mt-1 font-mono text-xs text-muted-foreground">{group.slug}</p></div><p className="max-w-md text-sm text-muted-foreground">{group.description ?? "No description supplied."}</p></div>)}</div>}
        </div>
      </div>
    </section>
  );
}
