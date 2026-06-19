const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getDashboardStats() {
  const [usersRes, forksRes, pluginsRes, healthRes] =
    await Promise.all([
      fetch(`${API_URL}/api/users`),
      fetch(`${API_URL}/api/forks`),
      fetch(`${API_URL}/api/plugins`),
      fetch(`${API_URL}/health`),
    ]);
    

  const users = await usersRes.json();
  const forks = await forksRes.json();
  const plugins = await pluginsRes.json();
  const health = await healthRes.json();

  return {
    members: users.length,
    forks: forks.length,
    plugins: plugins.length,
    apiStatus: health.status,
  };

}

export async function getRecentActivity() {
  const response = await fetch(
    `${API_URL}/api/audit?limit=5`
  );

  if (!response.ok) {
    throw new Error("Failed to load activity");
  }

  return response.json();
}

export async function getForks() {
  const response = await fetch(
    `${API_URL}/api/forks`
  );

  if (!response.ok) {
    throw new Error("Failed to load forks");
  }

  return response.json();
}