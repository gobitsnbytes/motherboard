// Sentry options shared by the browser, Node.js, and Edge runtimes.
// Only public, build-inlined values belong here: this file ships to the browser.
import type { BrowserOptions, ErrorEvent, EventHint } from "@sentry/nextjs";

type TransactionEvent = Parameters<NonNullable<BrowserOptions["beforeSendTransaction"]>>[0];

const FILTERED = "[Filtered]";
const SENSITIVE_KEY = /auth(?!or)|cookie|token|secret|passw|dsn|api[-_]?key|credential|private[-_]?key|webhook|(?:^|[-_])otp(?:$|[-_])/i;
const SECRET_PATTERNS: Array<[RegExp, string]> = [
  [/\bbearer\s+[A-Za-z0-9._~+/=-]+/gi, `Bearer ${FILTERED}`],
  // Credentials inside any URL: DSNs, database URLs, basic auth.
  [/([a-z][a-z0-9+.-]*:\/\/)[^/\s:@]+(?::[^/\s@]*)?@/gi, `$1${FILTERED}@`],
  // Signing, onboarding, and webhook tokens travel in the path.
  [/(\/sign\/|\/public\/|\/webhooks\/[^/\s]+\/)(?!:token|\{)[^/\s?#]+/gi, `$1${FILTERED}`],
  [/([?&][^=&\s]*(?:token|secret|key|sig|code|pass)[^=&\s]*=)[^&\s#]+/gi, `$1${FILTERED}`],
  [/[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b/g, "[email]"],
];
const SAFE_HEADERS = new Set(["user-agent", "content-type", "accept", "x-request-id", "host"]);

export function scrubText(value: string): string {
  return SECRET_PATTERNS.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), value);
}

function scrub(value: unknown, depth = 0): unknown {
  if (depth > 8) return FILTERED;
  if (typeof value === "string") return scrubText(value);
  if (Array.isArray(value)) return value.map((item) => scrub(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, SENSITIVE_KEY.test(key) ? FILTERED : scrub(item, depth + 1)]),
    );
  }
  return value;
}

function stripQuery(url: string): string {
  return scrubText(url.split(/[?#]/, 1)[0] ?? url);
}

function stripUrlData(data: Record<string, unknown>): Record<string, unknown> {
  for (const key of ["url", "to", "from", "http.url", "url.full"]) {
    if (typeof data[key] === "string") data[key] = stripQuery(data[key] as string);
  }
  delete data["http.query"];
  delete data["http.fragment"];
  delete data["url.query"];
  return data;
}

/** Strips secrets and personal data before an event leaves the process. */
export function beforeSend(event: ErrorEvent, _hint?: EventHint): ErrorEvent | null {
  const request = event.request;
  if (request) {
    delete request.cookies;
    delete request.data;
    delete request.query_string;
    if (request.url) request.url = stripQuery(request.url);
    if (request.headers) {
      request.headers = Object.fromEntries(
        Object.entries(request.headers).filter(([key]) => SAFE_HEADERS.has(key.toLowerCase())),
      );
    }
  }
  delete event.user;
  if (event.extra) event.extra = scrub(event.extra) as typeof event.extra;
  if (event.contexts) event.contexts = scrub(event.contexts) as typeof event.contexts;
  if (event.message) event.message = scrubText(event.message);
  for (const exception of event.exception?.values ?? []) {
    if (exception.value) exception.value = scrubText(exception.value);
  }
  for (const crumb of event.breadcrumbs ?? []) {
    if (crumb.message) crumb.message = scrubText(crumb.message);
    if (crumb.data) crumb.data = scrub(stripUrlData({ ...crumb.data })) as typeof crumb.data;
  }
  return event;
}

function sampleRate(raw: string | undefined, production: number): number {
  const parsed = raw ? Number(raw) : Number.NaN;
  if (Number.isFinite(parsed)) return Math.min(Math.max(parsed, 0), 1);
  return process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT === "production" ? production : 0;
}

export const sharedSentryOptions = {
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
  // SDK v11 dropped sendDefaultPii; every dataCollection field defaults to on.
  // userInfo: false also tells Sentry not to infer the client IP.
  dataCollection: {
    userInfo: false,
    cookies: false,
    httpHeaders: { request: { allow: ["user-agent", "content-type", "accept", "x-request-id"] }, response: false },
    httpBodies: [],
    urlQueryParams: false,
    graphQL: { document: false, variables: false },
    genAI: { inputs: false, outputs: false },
    databaseQueryData: false,
    queues: false,
    stackFrameVariables: false,
  },
  tracesSampleRate: sampleRate(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE, 0.05),
  // Browser noise that is never actionable.
  ignoreErrors: ["ResizeObserver loop limit exceeded", "ResizeObserver loop completed with undelivered notifications", "AbortError"],
  beforeSend,
  // v11 streams spans by default, which bypasses beforeSendTransaction. Static
  // mode keeps span scrubbing in the one hook below.
  traceLifecycle: "static" as const,
  beforeSendTransaction(event: TransactionEvent): TransactionEvent {
    if (event.request) {
      delete event.request.cookies;
      delete event.request.data;
      delete event.request.query_string;
      delete event.request.headers;
      if (event.request.url) event.request.url = stripQuery(event.request.url);
    }
    delete event.user;
    if (event.transaction) event.transaction = scrubText(event.transaction);
    for (const span of event.spans ?? []) {
      if (span.description) span.description = stripQuery(span.description);
      if (span.data) span.data = scrub(stripUrlData({ ...span.data })) as typeof span.data;
    }
    return event;
  },
};
