"use client";
import { Users, GitBranch, Puzzle, RefreshCw, Handshake, Plus, UserPlus, Loader2, Copy } from "lucide-react";
import StatCard from "components/dashboard/StatCard";
import Link from "next/link";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Input,
  Label,
} from "@bnb/ui";
import { useEffect, useState } from "react";
import { getDashboardStats, getRecentActivity, getForks } from "lib/dashboard";

export function OverviewContent() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [createForkOpen, setCreateForkOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [creatingFork, setCreatingFork] = useState(false);
  const [forkForm, setForkForm] = useState({
    slug: "",
    city_name: "",
    discord_city_role_id: "",
    discord_contributor_role_id: "",
  });

  const [stats, setStats] = useState({
    members: 0,
    forks: 0,
    plugins: 0,
    dyslexicCompanies: 0,
    apiStatus: "loading",
    databaseStatus: "loading",
    discordStatus: "loading",
    syncStatus: "loading",
  });
  const [activity, setActivity] = useState<any[]>([]);
  const [forks, setForks] = useState<any[]>([]);
  const loadDashboard = async () => {
    setLoading(true);
    try {
      const [statsData, activityData, forksData] = await Promise.all([
        getDashboardStats(),
        getRecentActivity(),
        getForks(),
      ]);

      setStats(statsData);
      setActivity(activityData);
      setForks(forksData);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const handleRunSync = async () => {
    setSyncing(true);
    try {
      const response = await fetch("/api/sync/trigger", { method: "POST" });
      if (response.ok) {
        alert("Sync triggered successfully!");
        loadDashboard();
      } else {
        const err = await response.json();
        alert(`Failed to trigger sync: ${err.detail || response.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert("An error occurred triggering the sync.");
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateFork = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingFork(true);
    try {
      const payload: any = {
        slug: forkForm.slug,
        city_name: forkForm.city_name,
      };
      if (forkForm.discord_city_role_id) payload.discord_city_role_id = forkForm.discord_city_role_id;
      if (forkForm.discord_contributor_role_id) payload.discord_contributor_role_id = forkForm.discord_contributor_role_id;

      const response = await fetch("/api/forks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        alert("Fork created successfully!");
        setCreateForkOpen(false);
        setForkForm({ slug: "", city_name: "", discord_city_role_id: "", discord_contributor_role_id: "" });
        loadDashboard();
      } else {
        const err = await response.json();
        alert(`Failed to create fork: ${err.detail || response.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert("An error occurred creating the fork.");
    } finally {
      setCreatingFork(false);
    }
  };
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Members"
          value={loading ? "..." : stats.members}
          description="Total registered"
          icon={<Users className="size-5" />}
        />

        <StatCard
          title="Forks"
          value={loading ? "..." : stats.forks}
          description="Active locations"
          icon={<GitBranch className="size-5" />}
        />

        <StatCard
          title="Plugins"
          value={loading ? "..." : stats.plugins}
          description="Installed"
          icon={<Puzzle className="size-5" />}
        />

        <Link href="/dashboard/dyslexic" className="block transition-transform hover:-translate-y-0.5">
          <StatCard
            title="Dyslexic"
            value={loading ? "..." : stats.dyslexicCompanies}
            description="Sponsorship pipeline"
            icon={<Handshake className="size-5 text-primary" />}
          />
        </Link>
      </div>
      <Card>
        <CardContent className="py-6">
          <h2 className="text-xl font-heading font-bold">Welcome back 👋</h2>

          <p className="text-sm text-muted-foreground mt-2">
            Manage members, forks, plugins, and organization operations from a
            single place.
          </p>
        </CardContent>
      </Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-3">
              {loading ? (
                <div>Loading activity...</div>
              ) : (
                activity.map((item, index) => (
                  <div key={index} className="flex justify-between">
                    <span>{item.action}</span>

                    <span className="text-xs text-muted-foreground">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span>API</span>

                <Badge
                  variant={stats.apiStatus === "ok" ? "success" : "danger"}
                >
                  {stats.apiStatus === "ok" ? "Online" : "Offline"}
                </Badge>
              </div>

              <div className="flex justify-between">
                <span>Database</span>
                <Badge
                  variant={stats.databaseStatus === "healthy" ? "success" : stats.databaseStatus === "loading" ? "neutral" : "danger"}
                >
                  {stats.databaseStatus === "healthy" ? "Healthy" : stats.databaseStatus === "loading" ? "Loading..." : "Degraded"}
                </Badge>
              </div>

              <div className="flex justify-between">
                <span>Discord</span>
                <Badge
                  variant={stats.discordStatus === "connected" ? "success" : stats.discordStatus === "unconfigured" ? "neutral" : stats.discordStatus === "loading" ? "neutral" : "danger"}
                >
                  {stats.discordStatus === "connected" ? "Connected" : stats.discordStatus === "unconfigured" ? "Unconfigured" : stats.discordStatus === "loading" ? "Loading..." : "Disconnected"}
                </Badge>
              </div>

              <div className="flex justify-between">
                <span>Sync</span>
                <Badge
                  variant={stats.syncStatus === "healthy" ? "success" : stats.syncStatus === "syncing" ? "warning" : stats.syncStatus === "no_runs" ? "neutral" : stats.syncStatus === "loading" ? "neutral" : "danger"}
                >
                  {stats.syncStatus === "healthy" ? "Healthy" : stats.syncStatus === "syncing" ? "Syncing" : stats.syncStatus === "no_runs" ? "No Runs" : stats.syncStatus === "loading" ? "Loading..." : "Unhealthy"}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Fork Health</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="space-y-3">
            {loading ? (
              <div>Loading forks...</div>
            ) : (
              forks.map((fork) => {
                const score = fork.health_score ?? 100;
                const isHealthy = score >= 70;
                const isWarning = score >= 50 && score < 70;
                const variant = isHealthy ? "success" : isWarning ? "warning" : "danger";
                const label = isHealthy ? `Healthy (${score}/100)` : isWarning ? `Audit Required (${score}/100)` : `Critical (${score}/100)`;

                return (
                  <div key={fork.id} className="flex justify-between items-center">
                    <span className="font-bold text-xs">{fork.city_name || fork.name}</span>
                    <Badge variant={variant}>{label}</Badge>
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <Dialog open={createForkOpen} onOpenChange={setCreateForkOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="size-4 mr-2" />
                  Create Fork
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Fork</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateFork} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="slug">Slug *</Label>
                    <Input id="slug" required value={forkForm.slug} onChange={(e) => setForkForm(prev => ({...prev, slug: e.target.value}))} placeholder="e.g. blr" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="city_name">City Name *</Label>
                    <Input id="city_name" required value={forkForm.city_name} onChange={(e) => setForkForm(prev => ({...prev, city_name: e.target.value}))} placeholder="e.g. Bangalore" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="discord_city_role_id">Discord City Role ID (optional)</Label>
                    <Input id="discord_city_role_id" value={forkForm.discord_city_role_id} onChange={(e) => setForkForm(prev => ({...prev, discord_city_role_id: e.target.value}))} placeholder="e.g. 1234567890" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="discord_contributor_role_id">Discord Contributor Role ID (optional)</Label>
                    <Input id="discord_contributor_role_id" value={forkForm.discord_contributor_role_id} onChange={(e) => setForkForm(prev => ({...prev, discord_contributor_role_id: e.target.value}))} placeholder="e.g. 0987654321" />
                  </div>
                  <Button type="submit" className="w-full" disabled={creatingFork}>
                    {creatingFork ? <Loader2 className="mr-2 size-4 animate-spin" /> : "Create"}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>

            <Button onClick={handleRunSync} disabled={syncing}>
              {syncing ? <Loader2 className="size-4 mr-2 animate-spin" /> : <RefreshCw className="size-4 mr-2" />}
              {syncing ? "Syncing..." : "Run Sync"}
            </Button>

            <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
              <DialogTrigger asChild>
                <Button>
                  <UserPlus className="size-4 mr-2" />
                  Invite Member
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Invite Member</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Share this invite link with new members to let them join the bits&bytes Discord server.
                  </p>
                  <div className="flex gap-2 items-center">
                    <Input readOnly value="https://discord.gg/bitsnbytes" className="flex-1" />
                    <Button variant="secondary" size="icon" onClick={() => {
                      navigator.clipboard.writeText("https://discord.gg/bitsnbytes");
                      alert("Copied to clipboard!");
                    }}>
                      <Copy className="size-4" />
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
