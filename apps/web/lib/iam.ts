const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getGroups() {
  const response = await fetch(
    `${API_URL}/api/iam/groups`
  );

  if (!response.ok) {
    throw new Error("Failed to load groups");
  }

  return response.json();
}

export async function getPermissions() {
  const response = await fetch(
    `${API_URL}/api/iam/permissions`
  );

  if (!response.ok) {
    throw new Error("Failed to load permissions");
  }

  return response.json();
}

export async function getDiscordMappings() {
  const response = await fetch(
    `${API_URL}/api/iam/discord-mappings`
  );

  if (!response.ok) {
    throw new Error("Failed to load mappings");
  }

  return response.json();
}