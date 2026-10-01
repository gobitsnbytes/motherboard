import { expect, test } from "bun:test";
import { type EffectiveAccess, hasAnyAccess } from "./access";
import { loadOverview } from "./overview";

const access: EffectiveAccess = {
  principal: { user_id: "lead", group_ids: [], is_super_admin: false },
  grants: [], groups: [],
  capabilities: ["iam.users.read", "plugins.read"],
  scoped_capabilities: [{ permission_key: "forks.read", resource_scope: "fork:nagpur", grant_id: "grant" }],
  fork_assignments: [{ fork_id: "nagpur", slug: "nagpur", city_name: "Nagpur", local_role: "fork_lead" }],
};

test("overview preserves successful sections when another request fails", async () => {
  const original = globalThis.fetch;
  const called: string[] = [];
  globalThis.fetch = (async (url: string | URL | Request) => {
    const path = String(url);
    called.push(path);
    if (path === "/api/plugins") return new Response("failed", { status: 500 });
    if (path === "/api/users") return Response.json([{ id: "person" }]);
    if (path === "/api/forks") return Response.json([{ slug: "nagpur" }]);
    return Response.json({});
  }) as typeof fetch;
  try {
    const result = await loadOverview(access);
    expect(result.stats.members).toBe(1);
    expect(result.stats.forks).toBe(1);
    expect(result.stats.plugins).toBeNull();
    expect(result.states.plugins).toBe("unavailable");
    expect(result.states.activity).toBe("restricted");
    expect(called.some((path) => path.includes("audit"))).toBe(false);
  } finally { globalThis.fetch = original; }
});

test("scoped capabilities require an active matching assignment", () => {
  expect(hasAnyAccess(access, "forks.read")).toBe(true);
  expect(hasAnyAccess({ ...access, fork_assignments: [] }, "forks.read")).toBe(false);
  expect(hasAnyAccess(access, "iam.grants.write")).toBe(false);
});
