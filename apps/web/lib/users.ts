const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getUsers() {
  const response = await fetch(
    `${API_URL}/api/users`
  );

  if (!response.ok) {
    throw new Error("Failed to load users");
  }

  return response.json();
}