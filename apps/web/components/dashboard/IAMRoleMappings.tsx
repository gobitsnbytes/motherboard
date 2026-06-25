"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@bnb/ui";

interface DiscordRole {
  id: string;
  name: string;
  color: number;
  hoist: boolean;
  position: number;
  permissions: string;
  managed: boolean;
  mentionable: boolean;
}

interface Group {
  id: string;
  slug: string;
  name: string;
  description?: string;
  is_system: boolean;
}

interface DiscordRoleMapping {
  id: string;
  discord_role_id: string;
  discord_role_name: string;
  group_id: string;
  sync_enabled: boolean;
  priority: number;
}

const API_BASE = "/api";

function getHeaders() {
  return {
    "Content-Type": "application/json",
  };
}

export default function IAMRoleMappings() {
  const [roles, setRoles] = useState<DiscordRole[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [mappings, setMappings] = useState<Record<string, DiscordRoleMapping>>({});
  const [selectedGroups, setSelectedGroups] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingRoleId, setSavingRoleId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    const headers = getHeaders();
    Promise.all([
      fetch(`${API_BASE}/iam/groups`, { headers }).then(async (res) => {
        if (!res.ok) {
          throw new Error(`Could not load groups: ${res.status}`);
        }
        return res.json();
      }),
      fetch(`${API_BASE}/iam/discord-roles`, { headers }).then(async (res) => {
        if (!res.ok) {
          throw new Error(`Could not load Discord roles: ${res.status}`);
        }
        return res.json();
      }),
      fetch(`${API_BASE}/iam/discord-mappings`, { headers }).then(async (res) => {
        if (!res.ok) {
          throw new Error(`Could not load role mappings: ${res.status}`);
        }
        return res.json();
      }),
    ])
      .then(([groupsData, rolesData, mappingsData]) => {
        setGroups(groupsData ?? []);
        setRoles(rolesData ?? []);
        const mappingRecords: Record<string, DiscordRoleMapping> = {};
        (mappingsData ?? []).forEach((mapping: DiscordRoleMapping) => {
          mappingRecords[mapping.discord_role_id] = mapping;
        });
        setMappings(mappingRecords);
        const selected: Record<string, string> = {};
        (rolesData ?? []).forEach((role: DiscordRole) => {
          selected[role.id] = mappingRecords[role.id]?.group_id ?? "";
        });
        setSelectedGroups(selected);
      })
      .catch((err) => {
        setError(err.message ?? "Unable to load IAM role mappings.");
      })
      .finally(() => setLoading(false));
  }, []);

  const sortedRoles = useMemo(
    () => [...roles].sort((a, b) => b.position - a.position),
    [roles],
  );

  const mappingByRole = useMemo(() => mappings, [mappings]);

  const groupOptions = useMemo(
    () => groups.map((group) => ({
      id: group.id,
      label: group.name,
      description: group.description,
      isSystem: group.is_system,
    })),
    [groups],
  );

  const getRowStatus = (roleId: string) => {
    if (savingRoleId === roleId) {
      return "Saving...";
    }
    return null;
  };

  const handleGroupChange = (roleId: string, groupId: string) => {
    setSelectedGroups((current) => ({ ...current, [roleId]: groupId }));
    setSuccessMessage(null);
  };

  const handleSave = async (role: DiscordRole) => {
    const selectedGroupId = selectedGroups[role.id] ?? "";
    if (!selectedGroupId) {
      return;
    }

    const currentMapping = mappingByRole[role.id];
    if (currentMapping?.group_id === selectedGroupId && currentMapping.discord_role_name === role.name) {
      return;
    }

    setSavingRoleId(role.id);
    setError(null);
    setSuccessMessage(null);

    const payload = {
      discord_role_id: role.id,
      discord_role_name: role.name,
      group_id: selectedGroupId,
      sync_enabled: true,
      priority: 0,
    };

    try {
      const response = await fetch(`${API_BASE}/iam/discord-mappings`, {
        method: "PUT",
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Failed to save mapping: ${response.status} ${body}`);
      }

      const updatedMapping: DiscordRoleMapping = await response.json();
      setMappings((current) => ({ ...current, [updatedMapping.discord_role_id]: updatedMapping }));
      setSuccessMessage(`Saved mapping for ${role.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save mapping.");
    } finally {
      setSavingRoleId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-base border-2 border-border bg-[#111] p-6">
        <div>
          <h2 className="text-xl font-heading font-bold text-foreground">Discord Role Mapping</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Bind Discord guild roles to internal operational groups. Save each mapping individually.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2 text-sm text-foreground/80">
            <span>{groups.length} groups</span>
            <span>{roles.length} Discord roles</span>
          </div>
          <div className="flex flex-wrap gap-2 text-sm text-foreground/80">
            <Badge variant="neutral">No optimistic updates</Badge>
            <Badge variant="neutral">Blocking spinner on save</Badge>
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-base border-2 border-border bg-[#111] p-4 text-sm text-foreground">
          <p className="font-medium text-main-foreground">Unable to load role mapping data.</p>
          <p className="mt-2 text-foreground/80">{error}</p>
        </div>
      ) : null}

      {successMessage ? (
        <div className="rounded-base border-2 border-border bg-[#111] p-4 text-sm text-foreground text-foreground/90">
          {successMessage}
        </div>
      ) : null}

      <div className="rounded-base border-2 border-border bg-[#111] p-4">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-1/3" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Discord Role</TableHeader>
                <TableHeader>Role ID</TableHeader>
                <TableHeader>Mapped Group</TableHeader>
                <TableHeader>Action</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedRoles.map((role) => {
                const selectedGroupId = selectedGroups[role.id] ?? "";
                const currentMapping = mappingByRole[role.id];
                const isUnchanged = currentMapping?.group_id === selectedGroupId;
                return (
                  <TableRow key={role.id}>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <span className="font-medium text-foreground">{role.name}</span>
                        <span className="text-xs text-muted-foreground">Position {role.position}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-mono text-xs text-foreground/70">{role.id}</span>
                    </TableCell>
                    <TableCell>
                      <div className="max-w-[260px]">
                        <Select value={selectedGroupId} onValueChange={(value) => handleGroupChange(role.id, value)}>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select group" />
                          </SelectTrigger>
                          <SelectContent>
                            {groupOptions.map((group) => (
                              <SelectItem key={group.id} value={group.id}>
                                <span>{group.label}</span>
                                {group.isSystem ? <span className="text-xs text-muted-foreground"> (system)</span> : null}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                        <Button
                          type="button"
                          size="sm"
                          disabled={!selectedGroupId || isUnchanged || savingRoleId === role.id}
                          onClick={() => handleSave(role)}
                        >
                          {savingRoleId === role.id ? "Saving…" : isUnchanged ? "Saved" : "Save"}
                        </Button>
                        {currentMapping && (
                          <span className="text-xs text-muted-foreground">
                            mapped to {groups.find((group) => group.id === currentMapping.group_id)?.name ?? currentMapping.group_id}
                          </span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
