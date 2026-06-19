const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getAuditLogs() {
  const response = await fetch(
    `${API_URL}/api/audit?limit=50`
  );

  if (!response.ok) {
    throw new Error("Failed to load audit logs");
  }

  return response.json();
}