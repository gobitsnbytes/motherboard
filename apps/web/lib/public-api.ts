const PUBLIC_ROUTE_PREFIXES = new Set(["forms", "calendar", "meetings", "onboarding"]);

export function isPublicApiRoute(path: readonly string[], inboundPath: string): boolean {
  if (inboundPath === "/health") return true;
  if (path[0] === "signatures" && (path[1] === "sign" || path[1] === "verify")) return true;
  if (path[0] === "signatures" && path[1] === "requests" && path[3] === "compliance-check") return true;
  if (path[0] === "calendar" && path[1] === "webhooks" && path[2] === "calcom") return true;
  const resource = path[0];
  return resource !== undefined && path[1] === "public" && PUBLIC_ROUTE_PREFIXES.has(resource);
}
