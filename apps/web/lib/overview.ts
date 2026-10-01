import { type EffectiveAccess, hasAccess, hasAnyAccess } from "./access";

export type SectionState = "ready" | "restricted" | "unavailable";
type Section<T> = { state: SectionState; data: T | null };

async function read<T>(url: string, allowed: boolean): Promise<Section<T>> {
  if (!allowed) return { state: "restricted", data: null };
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (response.status === 403) return { state: "restricted", data: null };
    if (!response.ok) return { state: "unavailable", data: null };
    return { state: "ready", data: await response.json() };
  } catch { return { state: "unavailable", data: null }; }
}

export async function loadOverview(access: EffectiveAccess) {
  const [users, forks, plugins, health, dyslexic, activity, actionItems] = await Promise.all([
    read<unknown[]>("/api/users", hasAccess(access, "iam.users.read")),
    read<any[]>("/api/forks", hasAnyAccess(access, "forks.read")),
    read<unknown[]>("/api/plugins", hasAccess(access, "plugins.read")),
    read<Record<string, string>>("/api/health/status", true),
    read<{ companies: number }>("/api/dyslexic/stats", true),
    read<any[]>("/api/audit?limit=5", hasAccess(access, "audit.read")),
    read<import("./dashboard").MyActionItem[]>("/api/meetings/action-items/mine", hasAccess(access, "meetings.read")),
  ]);
  return {
    stats: {
      members: users.data?.length ?? null, forks: forks.data?.length ?? null,
      plugins: plugins.data?.length ?? null, dyslexicCompanies: dyslexic.data?.companies ?? null,
      apiStatus: health.data?.status ?? "unknown", databaseStatus: health.data?.database ?? "unknown",
      discordStatus: health.data?.discord ?? "unknown", syncStatus: health.data?.sync ?? "unknown",
    },
    activity: activity.data ?? [], forks: forks.data ?? [], actionItems: actionItems.data ?? [],
    states: { members: users.state, forks: forks.state, plugins: plugins.state,
      dyslexic: dyslexic.state, activity: activity.state, actionItems: actionItems.state, health: health.state },
  };
}
