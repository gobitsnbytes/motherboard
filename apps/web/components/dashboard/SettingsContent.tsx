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
    version: "0.2.0",
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
        <Card className="border-2 border-border bg-[#141418] shadow-dark rounded-base">
          <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              Organization Settings
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-3.5 pt-4 font-mono text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Organization</span>
              <span className="font-bold text-white">bits&bytes™</span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Legal Entity</span>
              <span className="font-bold text-white">GOBITSNBYTES FOUNDATION</span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Region</span>
              <span className="font-bold text-white">India (Section 8)</span>
            </div>

            <div className="flex justify-between items-center py-1">
              <span className="text-zinc-400">Status</span>
              <span className="px-2 py-0.5 rounded-base text-[10px] font-bold border border-emerald-800 bg-emerald-950 text-emerald-400">
                Active &amp; Compliant
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Discord */}
        <Card className="border-2 border-border bg-[#141418] shadow-dark rounded-base">
          <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              Discord Integration
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-3.5 pt-4 font-mono text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Guild Status</span>
              <span className={`px-2 py-0.5 rounded-base text-[10px] font-bold border ${statusData.discord === "connected" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-zinc-800 text-zinc-400 border-zinc-700"}`}>
                {statusData.discord === "connected" ? "Connected" : statusData.discord === "unconfigured" ? "Unconfigured" : "Disconnected"}
              </span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Bot Status</span>
              <span className={`px-2 py-0.5 rounded-base text-[10px] font-bold border ${statusData.discord === "connected" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-red-950 text-red-400 border-red-800"}`}>
                {statusData.discord === "connected" ? "Online" : "Offline"}
              </span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Last Sync</span>
              <span className="text-zinc-200">{loading ? "..." : formatRelativeTime(statusData.last_sync_at)}</span>
            </div>

            <button 
              type="button"
              className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 font-heading font-black text-xs uppercase tracking-wider bg-orange text-black border-2 border-black rounded-base shadow-light hover:translate-x-[1px] hover:translate-y-[1px] transition-all disabled:opacity-50" 
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
            </button>
          </CardContent>
        </Card>
      </div>

      {/* Middle Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Security */}
        <Card className="border-2 border-border bg-[#141418] shadow-dark rounded-base">
          <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              Security &amp; Access
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-3.5 pt-4 font-mono text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">IAM Groups</span>
              <span className="font-bold text-white">{loading ? "--" : statusData.groups_count}</span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Permissions</span>
              <span className="font-bold text-white">{loading ? "--" : statusData.permissions_count}</span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Role Mappings</span>
              <span className="font-bold text-white">{loading ? "--" : statusData.role_mappings_count}</span>
            </div>

            <div className="flex gap-3 pt-2">
              <a 
                href="/dashboard/iam"
                className="flex-1 text-center px-4 py-2 font-mono font-bold text-xs uppercase bg-[#181820] text-zinc-200 border-2 border-border rounded-base shadow-light hover:bg-[#202028]"
              >
                Open IAM
              </a>

              <a 
                href="/dashboard/audit"
                className="flex-1 text-center px-4 py-2 font-mono font-bold text-xs uppercase bg-[#181820] text-zinc-200 border-2 border-border rounded-base shadow-light hover:bg-[#202028]"
              >
                Audit Log
              </a>
            </div>
          </CardContent>
        </Card>

        {/* System */}
        <Card className="border-2 border-border bg-[#141418] shadow-dark rounded-base">
          <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              System Telemetry
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-3.5 pt-4 font-mono text-xs">
            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Version</span>
              <span className="font-bold text-orange">v{loading ? "..." : statusData.version}</span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">Environment</span>
              <span className={`px-2 py-0.5 rounded-base text-[10px] font-bold border ${statusData.environment.toLowerCase() === "production" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-amber-950 text-amber-400 border-amber-800"}`}>
                {loading ? "..." : statusData.environment.charAt(0).toUpperCase() + statusData.environment.slice(1)}
              </span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-border/50">
              <span className="text-zinc-400">API Status</span>
              <span className={`px-2 py-0.5 rounded-base text-[10px] font-bold border ${statusData.database === "healthy" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-red-950 text-red-400 border-red-800"}`}>
                {loading ? "..." : "Online"}
              </span>
            </div>

            <div className="flex justify-between items-center py-1">
              <span className="text-zinc-400">Database</span>
              <span className={`px-2 py-0.5 rounded-base text-[10px] font-bold border ${statusData.database === "healthy" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-red-950 text-red-400 border-red-800"}`}>
                {loading ? "..." : statusData.database === "healthy" ? "Healthy (Postgres)" : "Degraded"}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Danger Zone */}
      <Card className="border-2 border-red-500 bg-[#141418] shadow-dark rounded-base">
        <CardHeader className="border-b-2 border-red-500 bg-red-950/40 py-3.5">
          <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-red-400">
            Danger Zone
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-4 pt-4">
          <p className="text-xs font-mono text-zinc-300">
            These actions require elevated Super Admin permissions and directly mutate caching or permission indexes.
          </p>

          <div className="flex flex-wrap gap-3">
            <button 
              type="button"
              onClick={handleResetCache} 
              disabled={actionLoading !== null || statusData.redis === "unconfigured"}
              className="px-4 py-2 font-mono font-bold text-xs uppercase bg-red-950 text-red-200 border-2 border-red-600 rounded-base shadow-light hover:bg-red-900 disabled:opacity-50"
            >
              {actionLoading === "cache" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin inline" />
                  Resetting...
                </>
              ) : (
                "Reset Redis Cache"
              )}
            </button>

            <button 
              type="button"
              onClick={handleRebuildPermissions} 
              disabled={actionLoading !== null}
              className="px-4 py-2 font-mono font-bold text-xs uppercase bg-red-950 text-red-200 border-2 border-red-600 rounded-base shadow-light hover:bg-red-900 disabled:opacity-50"
            >
              {actionLoading === "permissions" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin inline" />
                  Rebuilding...
                </>
              ) : (
                "Rebuild Permissions"
              )}
            </button>

            <button 
              type="button"
              onClick={handleClearSyncState} 
              disabled={actionLoading !== null}
              className="px-4 py-2 font-mono font-bold text-xs uppercase bg-red-950 text-red-200 border-2 border-red-600 rounded-base shadow-light hover:bg-red-900 disabled:opacity-50"
            >
              {actionLoading === "sync-state" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin inline" />
                  Clearing...
                </>
              ) : (
                "Clear Sync Run History"
              )}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}