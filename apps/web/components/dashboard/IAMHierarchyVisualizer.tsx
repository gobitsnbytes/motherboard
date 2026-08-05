"use client";

import React, { useEffect, useState } from "react";
import { Shield, ShieldAlert, Users, GitBranch, ArrowRight, RefreshCw, CheckCircle2, Lock, Sparkles, Layers } from "lucide-react";
import { Badge, Button } from "@bnb/ui";

interface IAMHierarchyGroup {
  id: string;
  name: string;
  slug: string;
  description?: string;
  is_system: boolean;
  grants_count: number;
  members_count: number;
  mapped_roles: {
    discord_role_id: string;
    discord_role_name: string;
    sync_enabled: boolean;
  }[];
}

export default function IAMHierarchyVisualizer() {
  const [data, setData] = useState<{
    groups: IAMHierarchyGroup[];
    total_groups: number;
    total_grants: number;
    total_mappings: number;
    total_memberships: number;
  } | null>(null);

  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<IAMHierarchyGroup | null>(null);

  const fetchHierarchy = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/iam/hierarchy");
      if (res.ok) {
        const hierarchyData = await res.json();
        setData(hierarchyData);
        if (hierarchyData.groups && hierarchyData.groups.length > 0) {
          setSelectedGroup(hierarchyData.groups[0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch IAM hierarchy:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHierarchy();
  }, []);

  const handleTriggerDiscordSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/sync/trigger", { method: "POST" });
      if (res.ok) {
        alert("Two-way Discord role sync triggered!");
        await fetchHierarchy();
      } else {
        const err = await res.json();
        alert(`Failed to trigger sync: ${err.detail || res.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert("Error triggering sync.");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border-2 border-border/50 bg-[#111] p-6 space-y-4 animate-pulse">
        <div className="h-6 w-48 bg-white/20 rounded" />
        <div className="h-4 w-96 bg-white/10 rounded" />
        <div className="grid grid-cols-4 gap-4 pt-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-white/10 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const systemLevels = [
    { level: "Level 0", title: "Super Admin", color: "border-red-500/60 bg-red-500/10 text-red-400" },
    { level: "Level 1", title: "Executive Board", color: "border-amber-500/60 bg-amber-500/10 text-amber-400" },
    { level: "Level 2", title: "Fork Leads & Officers", color: "border-blue-500/60 bg-blue-500/10 text-blue-400" },
    { level: "Level 3", title: "General Members", color: "border-emerald-500/60 bg-emerald-500/10 text-emerald-400" },
  ];

  return (
    <div className="space-y-6">
      {/* Header & Sync Controls */}
      <div className="rounded-xl border-2 border-border bg-[#111] p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-heading font-bold text-foreground">Diagrammatic IAM Hierarchy</h2>
            <Badge variant="success" className="text-[10px]">
              2-Way Discord Sync Active
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Visual breakdown of role inheritance, system groups, and Discord guild role bindings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button onClick={handleTriggerDiscordSync} disabled={syncing} size="sm">
            <RefreshCw className={`mr-2 size-3.5 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing Roles..." : "Trigger 2-Way Discord Sync"}
          </Button>
        </div>
      </div>

      {/* Level Hierarchy Diagram */}
      <div className="rounded-xl border-2 border-border bg-[#111] p-6 space-y-6">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-heading font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <Layers className="size-4 text-amber-400" /> Organizational Hierarchy Tree
          </h3>
          <span className="text-xs text-white/50">{data?.total_groups} Groups / {data?.total_mappings} Mapped Discord Roles</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
          {systemLevels.map((lvl, index) => {
            const levelGroups = (data?.groups || []).filter((g) => {
              if (index === 0) return g.slug.includes("admin");
              if (index === 1) return g.slug.includes("executive") || g.slug.includes("lead");
              if (index === 2) return !g.slug.includes("admin") && !g.slug.includes("member");
              return g.slug.includes("member") || g.slug.includes("user");
            });

            return (
              <div
                key={lvl.level}
                className={`rounded-xl border-2 p-4 space-y-3 transition-all ${lvl.color}`}
              >
                <div className="flex justify-between items-center border-b border-white/10 pb-2">
                  <span className="font-mono text-[10px] uppercase font-bold tracking-wider">{lvl.level}</span>
                  <Shield className="size-3.5" />
                </div>
                <h4 className="font-heading font-bold text-sm text-foreground">{lvl.title}</h4>

                <div className="space-y-2 pt-1">
                  {levelGroups.length === 0 ? (
                    <div className="text-[11px] text-muted-foreground italic">Standard group</div>
                  ) : (
                    levelGroups.map((g) => (
                      <div
                        key={g.id}
                        onClick={() => setSelectedGroup(g)}
                        className={`cursor-pointer rounded-lg border p-2.5 transition-all text-xs ${
                          selectedGroup?.id === g.id
                            ? "border-amber-400 bg-amber-400/20 text-foreground font-bold shadow-md"
                            : "border-white/10 bg-black/40 text-white/80 hover:border-white/30"
                        }`}
                      >
                        <div className="flex justify-between items-center">
                          <span className="truncate">{g.name}</span>
                          {g.is_system && <Badge variant="neutral" className="text-[9px]">system</Badge>}
                        </div>
                        {g.mapped_roles.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {g.mapped_roles.map((r) => (
                              <span key={r.discord_role_id} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                @{r.discord_role_name}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Group Permission & Discord Mapping Inspector */}
      {selectedGroup && (
        <div className="rounded-xl border-2 border-border bg-[#111] p-6 space-y-4">
          <div className="flex justify-between items-center border-b border-white/10 pb-4">
            <div>
              <h3 className="text-base font-heading font-bold text-foreground flex items-center gap-2">
                <Lock className="size-4 text-emerald-400" />
                Group Scope Inspector: {selectedGroup.name}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">{selectedGroup.description || "System operational group."}</p>
            </div>
            <div className="flex gap-2 font-mono text-xs">
              <Badge variant="neutral">{selectedGroup.grants_count} Granted Permissions</Badge>
              <Badge variant="neutral">{selectedGroup.members_count} Members</Badge>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4 text-xs">
            {/* Discord Mappings */}
            <div className="rounded-lg border border-white/10 bg-black/40 p-4 space-y-2">
              <h4 className="font-heading font-bold text-amber-400 uppercase text-[10px] tracking-wider">
                Linked Discord Roles
              </h4>
              {selectedGroup.mapped_roles.length === 0 ? (
                <p className="text-muted-foreground italic">No Discord roles linked to this group yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {selectedGroup.mapped_roles.map((m) => (
                    <div key={m.discord_role_id} className="flex justify-between items-center py-1 border-b border-white/5 font-mono">
                      <span>@{m.discord_role_name}</span>
                      <Badge variant={m.sync_enabled ? "success" : "neutral"} className="text-[9px]">
                        {m.sync_enabled ? "Auto-Sync On" : "Manual"}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Granted Scopes */}
            <div className="rounded-lg border border-white/10 bg-black/40 p-4 space-y-2">
              <h4 className="font-heading font-bold text-emerald-400 uppercase text-[10px] tracking-wider">
                Capabilities & Permissions Policy
              </h4>
              <ul className="space-y-1 font-mono text-[11px] text-white/80">
                <li className="flex items-center gap-2"><CheckCircle2 className="size-3.5 text-emerald-400" /> iam.groups.read</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="size-3.5 text-emerald-400" /> provisioning.sync.trigger</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="size-3.5 text-emerald-400" /> forks.members.write</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="size-3.5 text-emerald-400" /> dyslexic.companies.read</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
