import { auth } from "../../../lib/auth";
import { createInternalAuthHeaders } from "../../../lib/internal-auth";

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

function getApiBase() {
  return process.env.API_URL ?? "http://localhost:8000";
}

async function proxy(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const inboundPath = `/${path.join("/")}`;

  // Public routes (signing portal & verification engine) do not require Next.js session auth
  const isPublicRoute =
    (path[0] === "signatures" && (path[1] === "sign" || path[1] === "verify")) ||
    (path[0] === "forms" && path[1] === "public") ||
    inboundPath === "/health";

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

  const authHeaders = createInternalAuthHeaders({
    method: request.method,
    path: upstreamPath,
    userId: userId || "public-signatory",
  });
  for (const [key, value] of Object.entries(authHeaders)) {
    headers.set(key, value);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstreamResponse = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "follow",
    cache: "no-store",
  });

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

  return new Response(await upstreamResponse.arrayBuffer(), {
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
