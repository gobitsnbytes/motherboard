export async function getAuditLogs() {
  const response = await fetch(
    "/api/audit?limit=50"
  );

  if (!response.ok) {
    throw new Error("Failed to load audit logs");
  }

  return response.json();
}
