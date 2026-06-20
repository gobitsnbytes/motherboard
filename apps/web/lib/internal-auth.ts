import crypto from "crypto";

export function canonicalAuthPath(path: string) {
  return path.replace(/\/+$/, "") || "/";
}

export function createInternalAuthHeaders({
  method,
  path,
  userId,
}: {
  method: string;
  path: string;
  userId: string;
}) {
  const secret = process.env.API_INTERNAL_SECRET;
  if (!secret) {
    throw new Error("API_INTERNAL_SECRET is not configured");
  }

  const timestamp = Math.floor(Date.now() / 1000).toString();
  const message = `${timestamp}${method.toUpperCase()}${canonicalAuthPath(path)}${userId}`;
  const signature = crypto
    .createHmac("sha256", secret)
    .update(message)
    .digest("hex");

  return {
    "X-Internal-User-Id": userId,
    "X-Internal-Timestamp": timestamp,
    "X-Internal-Signature": signature,
  };
}

