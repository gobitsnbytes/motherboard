import { expect, test } from "bun:test";

import { beforeSend, beforeSendLog, scrubText, sharedSentryOptions } from "../sentry.shared";

test("only static operational logs with safe attributes leave the web runtime", () => {
  expect(beforeSendLog({ message: "private profile data", attributes: {} } as never)).toBeNull();
  const log = beforeSendLog({
    message: "web.api_proxy.failed",
    attributes: { failure: "timeout", status_code: 504, user: "private profile data" },
  } as never);
  expect(log?.attributes).toEqual({ failure: "timeout", status_code: 504 });
});

test("turns off every v11 data collection default", () => {
  const collection = sharedSentryOptions.dataCollection;
  expect(collection.userInfo).toBe(false);
  expect(collection.cookies).toBe(false);
  expect(collection.httpBodies).toEqual([]);
  expect(collection.urlQueryParams).toBe(false);
  expect(collection.stackFrameVariables).toBe(false);
  expect(sharedSentryOptions.tracesSampleRate).toBeGreaterThanOrEqual(0);
  expect(sharedSentryOptions.tracesSampleRate).toBeLessThanOrEqual(0.05);
});

test("scrubs request data, users, context, and breadcrumbs", () => {
  const event = beforeSend({
    type: undefined,
    user: { email: "person@example.org", ip_address: "10.0.0.1" },
    request: {
      url: "https://motherboard.test/sign/secret-token?otp=123",
      query_string: "otp=123",
      cookies: { session: "abc" },
      data: { password: "x" },
      headers: { Authorization: "Bearer abc", Cookie: "a=b", "User-Agent": "bun" },
    },
    extra: { accessToken: "t", note: "postgresql://user:pass@db/app" },
    exception: { values: [{ type: "Error", value: "mail to person@example.org failed" }] },
    breadcrumbs: [{ data: { url: "/api/users?token=abc" }, message: "Bearer abc" }],
  });

  expect(event?.user).toBeUndefined();
  expect(event?.request).toEqual({
    url: "https://motherboard.test/sign/[Filtered]",
    headers: { "User-Agent": "bun" },
  });
  expect(event?.extra).toEqual({ accessToken: "[Filtered]", note: "postgresql://[Filtered]@db/app" });
  expect(event?.exception?.values?.[0]?.value).toBe("mail to [email] failed");
  expect(event?.breadcrumbs?.[0]).toEqual({ data: { url: "/api/users" }, message: "Bearer [Filtered]" });
});

test("leaves route templates and version strings readable", () => {
  expect(scrubText("/api/signatures/sign/:token")).toBe("/api/signatures/sign/:token");
  expect(scrubText("@sentry/nextjs@11.0.0 failed")).toBe("@sentry/nextjs@11.0.0 failed");
});

test("scrubs transaction spans and keeps static trace lifecycle", () => {
  expect(sharedSentryOptions.traceLifecycle).toBe("static");
  const event = sharedSentryOptions.beforeSendTransaction({
    type: "transaction",
    transaction: "GET /sign/secret-token",
    request: { url: "https://m.test/x?token=1", headers: { Authorization: "Bearer a" } },
    spans: [
      {
        span_id: "1",
        trace_id: "2",
        start_timestamp: 0,
        description: "GET http://api.test/api/users?token=abc",
        data: { "url.full": "http://api.test/api/users?token=abc", "http.query": "token=abc" },
      },
    ],
  } as never);
  expect(event.transaction).toBe("GET /sign/[Filtered]");
  expect(event.request).toEqual({ url: "https://m.test/x" });
  expect(event.spans?.[0]?.description).toBe("GET http://api.test/api/users");
  expect(event.spans?.[0]?.data).toEqual({ "url.full": "http://api.test/api/users" });
});
