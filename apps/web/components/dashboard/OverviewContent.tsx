"use client";
import { Users, GitBranch, Puzzle, RefreshCw } from "lucide-react";
import StatCard from "components/dashboard/StatCard";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@bnb/ui";
import { Plus, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { getDashboardStats, getRecentActivity, getForks } from "lib/dashboard";

export function OverviewContent() {
  const [loading, setLoading] = useState(true);

  const [stats, setStats] = useState({
    members: 0,
    forks: 0,
    plugins: 0,
    apiStatus: "loading",
    databaseStatus: "loading",
    discordStatus: "loading",
    syncStatus: "loading",
  });
  const [activity, setActivity] = useState<any[]>([]);
  const [forks, setForks] = useState<any[]>([]);
  useEffect(() => {
    async function loadDashboard() {
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
    }

    loadDashboard();
  }, []);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Members"
          value={loading ? "..." : stats.members}
          description="+24 this week"
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
              forks.map((fork) => (
                <div key={fork.id} className="flex justify-between">
                  <span>{fork.city_name}</span>

                  <Badge variant="success">Healthy</Badge>
                </div>
              ))
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
            <Button>
              <Plus className="size-4" />
              Create Fork
            </Button>

            <Button>
              <RefreshCw className="size-4" />
              Run Sync
            </Button>

            <Button>
              <UserPlus className="size-4" />
              Invite Member
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
