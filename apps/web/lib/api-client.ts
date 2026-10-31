/**
 * Single browser-side client for the Motherboard API proxy.
 *
 * Pages used to turn every failed request into an empty list, so a 403 or a
 * timeout looked like "No vouchers". `api()` throws instead, and
 * `describeError()` turns the failure into a message the user can act on.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const RETRYABLE = new Set([502, 503, 504]);
const REQUEST_TIMEOUT_MS = 30_000;

/** Error text from a FastAPI error body. `detail` can be a string, a list (422) or an object; never render it raw. */
export function detailText(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg).filter(Boolean).join("; ") || fallback;
  }
  return (detail as { message?: string } | undefined)?.message ?? fallback;
}

async function attempt(path: string, init: RequestInit): Promise<Response> {
  return fetch(path, { cache: "no-store", ...init, signal: init.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const isGet = !init.method || init.method.toUpperCase() === "GET";
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type") && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const options = { ...init, headers };

  let response: Response;
  try {
    response = await attempt(path, options);
    // Reads are safe to repeat; one retry covers a worker restart or a slow cold start.
    if (isGet && RETRYABLE.has(response.status)) response = await attempt(path, options);
  } catch (error) {
    if (!isGet) throw toNetworkError(error);
    try {
      response = await attempt(path, options);
    } catch (second) {
      throw toNetworkError(second);
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, detailText(body, response.statusText || "Request failed"), (body as { code?: string } | null)?.code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function toNetworkError(error: unknown): ApiError {
  const timedOut = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
  return new ApiError(
    timedOut ? 504 : 503,
    timedOut ? "The server took too long to answer." : "Could not reach the server.",
    timedOut ? "upstream_timeout" : "upstream_unreachable",
  );
}

/** Message for the user. Never an empty state: say what went wrong and what to do. */
export function describeError(error: unknown, what = "this page"): string {
  if (!(error instanceof ApiError)) return `Could not load ${what}.`;
  if (error.status === 401) return "Your session has expired. Sign in again.";
  if (error.status === 403) return `You don't have access to ${what}. Ask a lead to grant it.`;
  if (error.status === 404) return `${what.charAt(0).toUpperCase()}${what.slice(1)} was not found.`;
  if (error.status >= 500 || error.status === 0) return `${error.message} Try again in a moment.`;
  return error.message;
}
