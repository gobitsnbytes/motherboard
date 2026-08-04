export async function getDashboardStats() {
  const [usersRes, forksRes, pluginsRes, healthRes, dyslexicRes] =
    await Promise.all([
      fetch("/api/users").catch(() => null),
      fetch("/api/forks").catch(() => null),
      fetch("/api/plugins").catch(() => null),
      fetch("/api/health/status").catch(() => null),
      fetch("/api/dyslexic/stats").catch(() => null),
    ]);

  const users = usersRes?.ok ? await usersRes.json() : [];
  const forks = forksRes?.ok ? await forksRes.json() : [];
  const plugins = pluginsRes?.ok ? await pluginsRes.json() : [];
  const health = healthRes?.ok ? await healthRes.json() : {};
  const dyslexic = dyslexicRes?.ok ? await dyslexicRes.json() : { companies: 0 };

  return {
    members: Array.isArray(users) ? users.length : 0,
    forks: Array.isArray(forks) ? forks.length : 0,
    plugins: Array.isArray(plugins) ? plugins.length : 0,
    dyslexicCompanies: dyslexic.companies ?? 0,
    apiStatus: health.status ?? "unknown",
    databaseStatus: health.database ?? "unknown",
    discordStatus: health.discord ?? "unknown",
    syncStatus: health.sync ?? "unknown",
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
