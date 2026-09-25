import { afterEach, beforeEach, expect, mock, test } from "bun:test";

const captured: Array<{ kind: "exception" | "message"; value: unknown; context: any }> = [];

mock.module("@sentry/nextjs", () => ({
  logger: { warn: () => {} },
  captureException: (value: unknown, context: unknown) => captured.push({ kind: "exception", value, context }),
  captureMessage: (value: unknown, context: unknown) => captured.push({ kind: "message", value, context }),
}));
mock.module("./auth", () => ({ auth: async () => ({ user: { internalUserId: "user-1" } }) }));

const { normalizeProxyRoute, shouldReportUpstreamStatus } = await import("./api-proxy-reporting");
const { GET } = await import("../app/api/[...path]/route");

const realFetch = globalThis.fetch;

function call(path: string[], query = "") {
  const request = new Request(`http://web.test/api/${path.join("/")}${query}`, {
    headers: { authorization: "Bearer browser-token", cookie: "session=abc" },
  });
  return GET(request, { params: Promise.resolve({ path }) });
}

beforeEach(() => {
  captured.length = 0;
  process.env.API_INTERNAL_SECRET = "test-secret";
  process.env.API_URL = "http://api.test";
});

afterEach(() => {
  globalThis.fetch = realFetch;
});

test("normalizes ids and path tokens out of proxy routes", () => {
  expect(normalizeProxyRoute(["signatures", "sign", "recipient-token-value"])).toBe("/signatures/sign/:token");
  expect(normalizeProxyRoute(["onboarding", "public", "abc"])).toBe("/onboarding/public/:token");
  expect(normalizeProxyRoute(["finance", "vouchers", "3f2b1c9e-8a7d-4e6f-9b0a-1c2d3e4f5a6b"])).toBe(
    "/finance/vouchers/:id",
  );
  expect(normalizeProxyRoute(["users", "42", "profile"])).toBe("/users/:id/profile");
});

test("only gateway failures the API cannot report are upstream issues", () => {
  expect(shouldReportUpstreamStatus(502)).toBe(true);
  expect(shouldReportUpstreamStatus(504)).toBe(true);
  for (const status of [200, 400, 401, 403, 404, 409, 422, 500, 503]) {
    expect(shouldReportUpstreamStatus(status)).toBe(false);
  }
});

test("reports an unreachable backend once with safe tags", async () => {
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed");
  }) as unknown as typeof fetch;

  const response = await call(["signatures", "sign", "secret-token"], "?otp=123");

  expect(response.status).toBe(503);
  expect(captured).toHaveLength(1);
  const [event] = captured;
  expect(event?.kind).toBe("exception");
  expect(event?.context.tags).toMatchObject({
    operation: "api_proxy",
    upstream: "bnb-api",
    "proxy.failure": "connection",
    "http.method": "GET",
    "http.route": "/signatures/sign/:token",
  });
  expect(JSON.stringify(event?.context)).not.toContain("secret-token");
  expect(JSON.stringify(event?.context)).not.toContain("otp");
});

test("reports timeouts as their own failure kind", async () => {
  globalThis.fetch = (async () => {
    throw new DOMException("timed out", "TimeoutError");
  }) as unknown as typeof fetch;

  const response = await call(["finance", "summary"]);

  expect(response.status).toBe(504);
  expect(captured[0]?.context.tags["proxy.failure"]).toBe("timeout");
});

test("does not report ordinary upstream 4xx or API-owned 5xx responses", async () => {
  for (const status of [400, 401, 403, 404, 422, 500, 503]) {
    globalThis.fetch = (async () => new Response("{}", { status })) as unknown as typeof fetch;
    const response = await call(["users", "me"]);
    expect(response.status).toBe(status);
  }
  expect(captured).toHaveLength(0);
});

test("reports gateway errors and interrupted bodies", async () => {
  globalThis.fetch = (async () => new Response("bad gateway", { status: 502 })) as unknown as typeof fetch;
  expect((await call(["users", "me"])).status).toBe(502);
  expect(captured[0]).toMatchObject({ kind: "message" });
  expect(captured[0]?.context.tags["http.status_code"]).toBe("502");

  captured.length = 0;
  const broken = new Response("ok", { status: 200 });
  broken.arrayBuffer = async () => {
    throw new Error("socket hang up");
  };
  globalThis.fetch = (async () => broken) as unknown as typeof fetch;
  expect((await call(["users", "me"])).status).toBe(502);
  expect(captured[0]?.context.tags["proxy.failure"]).toBe("body_read");
});
