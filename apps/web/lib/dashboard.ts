export async function getDashboardStats() {
  const [usersRes, forksRes, pluginsRes, healthRes] =
    await Promise.all([
      fetch("/api/users"),
      fetch("/api/forks"),
      fetch("/api/plugins"),
      fetch("/api/health"),
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
    "/api/audit?limit=5"
  );

  if (!response.ok) {
    throw new Error("Failed to load activity");
  }

  return response.json();
}

export async function getForks() {
  const response = await fetch(
    "/api/forks"
  );

  if (!response.ok) {
    throw new Error("Failed to load forks");
  }

  return response.json();
}
