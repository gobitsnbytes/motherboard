import * as Sentry from "@sentry/nextjs";

export type ProxyFailure = "timeout" | "connection" | "body_read" | "bad_gateway";

// The API reports its own 500s to its Sentry project, and its 503s are
// deliberate (readiness, unconfigured providers). Only gateway failures the
// API cannot see are reported from here.
const REPORTED_UPSTREAM_STATUSES = new Set([502, 504]);

const ID_SEGMENT = /^(?:\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[A-Za-z0-9_-]{20,})$/i;
const TOKEN_PARENTS = new Set(["sign", "public", "calcom"]);

/** Collapses ids and path tokens so events group by route and never carry secrets. */
export function normalizeProxyRoute(segments: string[]): string {
  return `/${segments
    .map((segment, index) => {
      if (index > 0 && TOKEN_PARENTS.has(segments[index - 1] ?? "")) return ":token";
      return ID_SEGMENT.test(segment) ? ":id" : segment;
    })
    .join("/")}`;
}

export function shouldReportUpstreamStatus(status: number): boolean {
  return REPORTED_UPSTREAM_STATUSES.has(status);
}

export function reportProxyFailure(
  failure: ProxyFailure,
  context: { method: string; route: string; status?: number },
  error?: unknown,
): void {
  Sentry.logger.warn("web.api_proxy.failed", {
    failure,
    ...(context.status === undefined ? {} : { status_code: context.status }),
  });
  const tags = {
    operation: "api_proxy",
    upstream: "bnb-api",
    "proxy.failure": failure,
    "http.method": context.method,
    "http.route": context.route,
  };
  if (error !== undefined) {
    Sentry.captureException(error, { tags, level: "error" });
  } else {
    Sentry.captureMessage(`API proxy upstream ${context.status ?? "error"} on ${context.method} ${context.route}`, {
      tags: { ...tags, "http.status_code": String(context.status ?? "") },
      level: "error",
      fingerprint: ["api-proxy-upstream", String(context.status ?? ""), context.route],
    });
  }
}
