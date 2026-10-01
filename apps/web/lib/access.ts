export interface AccessGrant {
  id: string;
  principal_type: "user" | "group";
  principal_id: string;
  permission_key: string;
  resource_scope: string | null;
  expires_at: string | null;
}

export interface EffectiveAccess {
  principal: { user_id: string; group_ids: string[]; is_super_admin: boolean };
  grants: AccessGrant[];
  groups: Array<{ id: string; name: string; slug: string }>;
  capabilities: string[];
  scoped_capabilities: Array<{ permission_key: string; resource_scope: string; grant_id: string }>;
  fork_assignments: Array<{ fork_id: string; slug: string; city_name: string; local_role: string }>;
}

export function hasAccess(access: EffectiveAccess | null, permission: string, scope?: string): boolean {
  if (!access) return false;
  if (access.principal.is_super_admin || access.capabilities.includes(permission)) return true;
  return scope !== undefined && access.scoped_capabilities.some(
    (entry) => entry.permission_key === permission && entry.resource_scope === scope,
  );
}

export function hasAnyAccess(access: EffectiveAccess | null, permission: string): boolean {
  return hasAccess(access, permission) || Boolean(access?.scoped_capabilities.some(
    (entry) => entry.permission_key === permission && access.fork_assignments.some(
      (fork) => `fork:${fork.slug}` === entry.resource_scope && (!permission.endsWith(".write") || fork.local_role === "fork_lead"),
    ),
  ));
}
