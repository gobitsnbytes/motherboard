"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
} from "@bnb/ui";

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return "Never";
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  } catch (e) {
    return "Unknown";
  }
}

export function SettingsContent() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [statusData, setStatusData] = useState<{
    database: string;
    redis: string;
    discord: string;
    sync: string;
    last_sync_at: string | null;
    version: string;
    environment: string;
    groups_count: number;
    permissions_count: number;
    role_mappings_count: number;
  }>({
    database: "loading",
    redis: "loading",
    discord: "loading",
    sync: "loading",
    last_sync_at: null,
    version: "0.1.1",
    environment: "development",
    groups_count: 0,
    permissions_count: 0,
    role_mappings_count: 0,
  });

  const fetchStatus = async () => {
    try {
      const response = await fetch("/api/health/status");
      if (response.ok) {
        const data = await response.json();
        setStatusData(data);
      }
    } catch (e) {
      console.error("Failed to fetch settings status:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      const response = await fetch("/api/sync/trigger", { method: "POST" });
      if (response.ok) {
        alert("Manual sync triggered successfully!");
        await fetchStatus();
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

  const handleResetCache = async () => {
    if (!window.confirm("Are you sure you want to flush the Redis cache database?")) return;
    setActionLoading("cache");
    try {
      const response = await fetch("/api/admin/reset-cache", { method: "POST" });
      if (response.ok) {
        alert("Redis cache database flushed successfully.");
        await fetchStatus();
      } else {
        const err = await response.json();
        alert(`Failed to reset cache: ${err.detail || response.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert("An error occurred resetting the cache.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRebuildPermissions = async () => {
    if (!window.confirm("Are you sure you want to rebuild system permissions and role mappings?")) return;
    setActionLoading("permissions");
    try {
      const response = await fetch("/api/admin/rebuild-permissions", { method: "POST" });
      if (response.ok) {
        alert("System permissions and role mappings rebuilt successfully.");
        await fetchStatus();
      } else {
        const err = await response.json();
        alert(`Failed to rebuild permissions: ${err.detail || response.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert("An error occurred rebuilding permissions.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearSyncState = async () => {
    if (!window.confirm("Are you sure you want to clear the entire sync run history? This action is irreversible.")) return;
    setActionLoading("sync-state");
    try {
      const response = await fetch("/api/admin/clear-sync-state", { method: "POST" });
      if (response.ok) {
        alert("Sync run history cleared successfully.");
        await fetchStatus();
      } else {
        const err = await response.json();
        alert(`Failed to clear sync history: ${err.detail || response.statusText}`);
      }
    } catch (e) {
      console.error(e);
      alert("An error occurred clearing sync history.");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Organization */}
        <Card>
          <CardHeader>
            <CardTitle>Organization Settings</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Organization
              </span>
              <span>bits&bytes™</span>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Region
              </span>
              <span>India</span>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Status
              </span>
              <Badge>Active</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Discord */}
        <Card>
          <CardHeader>
            <CardTitle>Discord Integration</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Guild Status
              </span>
              <Badge variant={statusData.discord === "connected" ? "success" : statusData.discord === "unconfigured" ? "neutral" : "danger"}>
                {statusData.discord === "connected" ? "Connected" : statusData.discord === "unconfigured" ? "Unconfigured" : "Disconnected"}
              </Badge>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Bot Status
              </span>
              <Badge variant={statusData.discord === "connected" ? "success" : "danger"}>
                {statusData.discord === "connected" ? "Online" : "Offline"}
              </Badge>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">
                Last Sync
              </span>
              <span>{loading ? "..." : formatRelativeTime(statusData.last_sync_at)}</span>
            </div>

            <Button 
              className="w-full" 
              onClick={handleManualSync} 
              disabled={syncing || statusData.discord !== "connected"}
            >
              {syncing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing...
                </>
              ) : (
                "Run Manual Sync"
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Middle Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Security */}
        <Card>
          <CardHeader>
            <CardTitle>Security & Access</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span>IAM Groups</span>
              <span>{loading ? "--" : statusData.groups_count}</span>
            </div>

            <div className="flex justify-between">
              <span>Permissions</span>
              <span>{loading ? "--" : statusData.permissions_count}</span>
            </div>

            <div className="flex justify-between">
              <span>Role Mappings</span>
              <span>{loading ? "--" : statusData.role_mappings_count}</span>
            </div>

            <div className="flex gap-3 pt-2">
              <Button asChild>
                <a href="/dashboard/iam">
                  Open IAM
                </a>
              </Button>

              <Button asChild>
                <a href="/dashboard/audit">
                  Audit Log
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* System */}
        <Card>
          <CardHeader>
            <CardTitle>System Information</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span>Version</span>
              <span>{loading ? "..." : statusData.version}</span>
            </div>

            <div className="flex justify-between">
              <span>Environment</span>
              <Badge variant={statusData.environment.toLowerCase() === "production" ? "success" : "warning"}>
                {loading ? "..." : statusData.environment.charAt(0).toUpperCase() + statusData.environment.slice(1)}
              </Badge>
            </div>

            <div className="flex justify-between">
              <span>API</span>
              <Badge variant={statusData.database === "healthy" ? "success" : "danger"}>
                {loading ? "..." : "Online"}
              </Badge>
            </div>

            <div className="flex justify-between">
              <span>Database</span>
              <Badge variant={statusData.database === "healthy" ? "success" : "danger"}>
                {loading ? "..." : statusData.database === "healthy" ? "Healthy" : "Degraded"}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Danger Zone */}
      <Card>
        <CardHeader>
          <CardTitle>Danger Zone</CardTitle>
        </CardHeader>

        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            These actions require elevated permissions. Please handle with care.
          </p>

          <div className="flex flex-wrap gap-3">
            <Button 
              onClick={handleResetCache} 
              disabled={actionLoading !== null || statusData.redis === "unconfigured"}
            >
              {actionLoading === "cache" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resetting...
                </>
              ) : (
                "Reset Cache"
              )}
            </Button>

            <Button 
              onClick={handleRebuildPermissions} 
              disabled={actionLoading !== null}
            >
              {actionLoading === "permissions" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Rebuilding...
                </>
              ) : (
                "Rebuild Permissions"
              )}
            </Button>

            <Button 
              onClick={handleClearSyncState} 
              disabled={actionLoading !== null}
            >
              {actionLoading === "sync-state" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Clearing...
                </>
              ) : (
                "Clear Sync State"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}