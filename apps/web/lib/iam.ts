export async function getGroups() {
  const response = await fetch(
    "/api/iam/groups"
  );

  if (!response.ok) {
    throw new Error("Failed to load groups");
  }

  return response.json();
}

export async function getPermissions() {
  const response = await fetch(
    "/api/iam/permissions"
  );

  if (!response.ok) {
    throw new Error("Failed to load permissions");
  }

  return response.json();
}

export async function getDiscordMappings() {
  const response = await fetch(
    "/api/iam/discord-mappings"
  );

  if (!response.ok) {
    throw new Error("Failed to load mappings");
  }

  return response.json();
}

export async function getIamMe() {
  const response = await fetch("/api/iam/me", { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Unable to load your access (${response.status})`);
  }

  return response.json();
}
