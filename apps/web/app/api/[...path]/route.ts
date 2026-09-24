import { normalizeProxyRoute, reportProxyFailure, shouldReportUpstreamStatus } from "../../../lib/api-proxy-reporting";
import { auth } from "../../../lib/auth";
import { createInternalAuthHeaders } from "../../../lib/internal-auth";
import { isPublicApiRoute } from "../../../lib/public-api";

export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

const UPSTREAM_TIMEOUT_MS = 8_000;

function getApiBase() {
  return process.env.API_URL ?? "http://localhost:8000";
}

async function proxy(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const inboundPath = `/${path.join("/")}`;
  const failureContext = { method: request.method, route: normalizeProxyRoute(path) };

  const isPublicRoute = isPublicApiRoute(path, inboundPath);

  const session = await auth();
  const userId = session?.user?.internalUserId;
  if (!userId && !isPublicRoute) {
    return Response.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const upstreamPath = inboundPath === "/health" ? "/health" : `/api${inboundPath}`;
  const incomingUrl = new URL(request.url);
  const upstreamUrl = new URL(`${upstreamPath}${incomingUrl.search}`, getApiBase());

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("Content-Type", contentType);
  if (accept) headers.set("Accept", accept);
  for (const header of ["idempotency-key", "x-booking-token", "x-cal-signature-256", "x-form-upload-token"]) {
    const value = request.headers.get(header);
    if (value) headers.set(header, value);
  }

  const authHeaders = createInternalAuthHeaders({
    method: request.method,
    path: upstreamPath,
    userId: userId || "public-signatory",
  });
  for (const [key, value] of Object.entries(authHeaders)) {
    headers.set(key, value);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "follow",
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch (error) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    console.error("[api-proxy] upstream request failed", {
      route: failureContext.route,
      reason: timedOut ? "timeout" : "connection",
    });
    reportProxyFailure(timedOut ? "timeout" : "connection", failureContext, error);
    return Response.json(
      {
        detail: timedOut
          ? "The backend is responding slowly. Please retry."
          : "The backend is temporarily unreachable. Please retry.",
        code: timedOut ? "upstream_timeout" : "upstream_unreachable",
      },
      { status: timedOut ? 504 : 503 },
    );
  }

  if (shouldReportUpstreamStatus(upstreamResponse.status)) {
    reportProxyFailure("bad_gateway", { ...failureContext, status: upstreamResponse.status });
  }

  const responseHeaders = new Headers(upstreamResponse.headers);
  for (const header of HOP_BY_HOP_HEADERS) {
    responseHeaders.delete(header);
  }

  // Server-sent events must stream through. Buffering the body below would wait
  // for a response that never ends, so the connection would hang open forever
  // and no event would ever reach the browser.
  const upstreamType = upstreamResponse.headers.get("content-type") ?? "";
  if (upstreamType.startsWith("text/event-stream")) {
    responseHeaders.set("Cache-Control", "no-cache, no-transform");
    responseHeaders.set("Connection", "keep-alive");
    responseHeaders.set("X-Accel-Buffering", "no");
    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  }

  let body: ArrayBuffer;
  try {
    body = await upstreamResponse.arrayBuffer();
  } catch (error) {
    // The upstream closed or corrupted the response after sending headers.
    reportProxyFailure("body_read", { ...failureContext, status: upstreamResponse.status }, error);
    return Response.json(
      { detail: "The backend response was interrupted. Please retry.", code: "upstream_interrupted" },
      { status: 502 },
    );
  }

  return new Response(body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context);
}
