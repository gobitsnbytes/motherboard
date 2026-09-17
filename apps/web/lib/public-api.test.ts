import { expect, test } from "bun:test";

import { isPublicApiRoute } from "./public-api";

test("allows every supported public workflow through the API proxy", () => {
  for (const [path, inboundPath] of [
    [["forms", "public", "apply"], "/forms/public/apply"],
    [["calendar", "public", "community", "slots"], "/calendar/public/community/slots"],
    [["meetings", "public", "availability", "lead"], "/meetings/public/availability/lead"],
    [["onboarding", "public", "portal-token"], "/onboarding/public/portal-token"],
    [["signatures", "sign", "recipient-token"], "/signatures/sign/recipient-token"],
    [["signatures", "verify", "document-id"], "/signatures/verify/document-id"],
    [["signatures", "requests", "request-id", "compliance-check"], "/signatures/requests/request-id/compliance-check"],
    [["calendar", "webhooks", "calcom", "connection-id"], "/calendar/webhooks/calcom/connection-id"],
  ] as const) {
    expect(isPublicApiRoute(path, inboundPath)).toBe(true);
  }
});

test("does not make internal onboarding routes public", () => {
  expect(isPublicApiRoute(["onboarding", "cases"], "/onboarding/cases")).toBe(false);
  expect(isPublicApiRoute(["signatures", "requests", "request-id"], "/signatures/requests/request-id")).toBe(false);
});
