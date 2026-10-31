import { afterEach, describe, expect, test } from "bun:test";
import { api, ApiError, describeError, detailText } from "./api-client";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function stub(...responses: Array<Response | Error>) {
  const calls: string[] = [];
  globalThis.fetch = (async (url: string) => {
    calls.push(String(url));
    const next = responses.shift()!;
    if (next instanceof Error) throw next;
    return next;
  }) as unknown as typeof fetch;
  return calls;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("detailText", () => {
  test("handles string, validation list, object and missing detail", () => {
    expect(detailText({ detail: "nope" }, "x")).toBe("nope");
    expect(detailText({ detail: [{ msg: "a" }, { msg: "b" }] }, "x")).toBe("a; b");
    expect(detailText({ detail: { message: "m" } }, "x")).toBe("m");
    expect(detailText(null, "fallback")).toBe("fallback");
    expect(detailText({ detail: { other: 1 } }, "fallback")).toBe("fallback");
  });
});

describe("api", () => {
  test("a 403 throws instead of returning an empty list", async () => {
    stub(json({ detail: "Missing permission: finance.ledger.read" }, 403));
    const error = await api("/api/finance/vouchers").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(403);
    expect(describeError(error, "vouchers")).toContain("don't have access");
  });

  test("a GET retries once on 503 and succeeds", async () => {
    const calls = stub(json({ detail: "busy" }, 503), json([1, 2]));
    expect(await api("/api/x")).toEqual([1, 2]);
    expect(calls.length).toBe(2);
  });

  test("a POST is never retried", async () => {
    const calls = stub(json({ detail: "busy" }, 503), json({ ok: true }));
    await expect(api("/api/x", { method: "POST", body: "{}" })).rejects.toBeInstanceOf(ApiError);
    expect(calls.length).toBe(1);
  });

  test("a dead connection becomes a readable 503", async () => {
    stub(new TypeError("fetch failed"), new TypeError("fetch failed"));
    const error = await api("/api/x").catch((e) => e);
    expect(error.status).toBe(503);
    expect(describeError(error)).toContain("Could not reach the server");
  });

  test("204 returns undefined", async () => {
    stub(new Response(null, { status: 204 }));
    expect(await api("/api/x", { method: "DELETE" })).toBeUndefined();
  });
});
