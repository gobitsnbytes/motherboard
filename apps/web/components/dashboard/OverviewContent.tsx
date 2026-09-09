"use client";

import { Users, GitBranch, Puzzle, RefreshCw, Handshake, Plus, UserPlus, Loader2, Copy } from "lucide-react";
import Link from "next/link";
import StatCard from "components/dashboard/StatCard";
import { OverviewSkeleton } from "./Skeletons";
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
import {
  getDashboardStats,
  getRecentActivity,
  getForks,
  getMyActionItems,
  type MyActionItem,
} from "lib/dashboard";

export function OverviewContent() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [createForkOpen, setCreateForkOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [creatingFork, setCreatingFork] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; message: string } | null>(null);
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
  const [actionItems, setActionItems] = useState<MyActionItem[]>([]);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const [statsData, activityData, forksData, itemsData] = await Promise.all([
        getDashboardStats(),
        getRecentActivity(),
        getForks(),
        getMyActionItems().catch(() => [] as MyActionItem[]),
      ]);

      setStats(statsData);
      setActivity(activityData);
      setForks(forksData);
      setActionItems(itemsData);
    } catch (error) {
      setNotice({ kind: "error", message: "The overview could not load completely. Refresh to retry." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  if (loading) {
    return <OverviewSkeleton />;
  }

  const handleRunSync = async () => {
    setSyncing(true);
    setNotice(null);
    try {
      const response = await fetch("/api/sync/trigger", { method: "POST" });
      if (response.ok) {
        setNotice({ kind: "success", message: "Discord sync started. Refreshing operational data." });
        loadDashboard();
      } else {
        const err = await response.json();
        setNotice({ kind: "error", message: `Discord sync failed: ${err.detail || response.statusText}` });
      }
    } catch (e) {
      setNotice({ kind: "error", message: "Discord sync failed because the server could not be reached." });
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateFork = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingFork(true);
    setNotice(null);
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
        setNotice({ kind: "success", message: `City chapter ${forkForm.city_name} was created.` });
        setCreateForkOpen(false);
        setForkForm({ slug: "", city_name: "", discord_city_role_id: "", discord_contributor_role_id: "" });
        loadDashboard();
      } else {
        const err = await response.json();
        setNotice({ kind: "error", message: `City chapter could not be created: ${err.detail || response.statusText}` });
      }
    } catch (e) {
      setNotice({ kind: "error", message: "City chapter could not be created because the server could not be reached." });
    } finally {
      setCreatingFork(false);
    }
  };

  return (
    <div className="space-y-6">
      {notice ? (
        <div
          role="status"
          className={`border-2 px-4 py-3 text-sm font-mono ${notice.kind === "success" ? "border-[#265d3a] bg-[#eaf5ed] text-[#173d24]" : "border-[#97192c] bg-[#fbecef] text-[#5b0f1a]"}`}
        >
          {notice.message}
        </div>
      ) : null}

      {/* Top Stat Cards Grid */}
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
          description="Active city chapters"
          icon={<GitBranch className="size-5" />}
        />

        <StatCard
          title="Plugins"
          value={loading ? "..." : stats.plugins}
          description="Loaded extensions"
          icon={<Puzzle className="size-5" />}
        />

        <Link href="/dashboard/dyslexic" className="block">
          <StatCard
            title="Dyslexic"
            value={loading ? "..." : stats.dyslexicCompanies}
            description="Sponsorship pipeline"
            icon={<Handshake className="size-5" />}
          />
        </Link>
      </div>

      {/* Welcome Banner */}
      <Card className="border-2 border-border bg-[#141418] shadow-light">
        <CardContent className="py-5">
          <h2 className="text-xl font-heading font-black text-white uppercase tracking-tight">
            Welcome to Motherboard
          </h2>
          <p className="text-xs sm:text-sm text-zinc-300 font-base mt-1">
            Central operations layer: manage member IAM policies, city fork onboarding, digital signatures, and meetings.
          </p>
        </CardContent>
      </Card>

      {/* Activity & connected services */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="border-b-2 border-border pb-3 bg-[#121216]">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              Recent Activity
            </CardTitle>
          </CardHeader>

          <CardContent className="pt-4">
            <div className="space-y-2.5">
              {loading ? (
                <div className="text-xs text-zinc-400 font-mono">Loading activity...</div>
              ) : activity.length === 0 ? (
                <div className="text-xs text-zinc-400 font-mono">No recent activity logged.</div>
              ) : (
                activity.map((item, index) => (
                  <div key={index} className="flex justify-between items-center p-2.5 rounded-base border border-border bg-[#181820] text-xs">
                    <span className="font-mono text-zinc-200">{item.action}</span>
                    <span className="text-[11px] font-mono text-zinc-400">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="border-b-2 border-border pb-3 bg-[#121216]">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              Connected services
            </CardTitle>
          </CardHeader>

          <CardContent className="pt-4">
            <div className="space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center pb-2 border-b border-border">
                <span className="text-zinc-300">Motherboard API</span>
                <span className={`px-2 py-0.5 rounded-base border text-[10px] font-bold ${stats.apiStatus === "ok" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-red-950 text-red-400 border-red-800"}`}>
                  {stats.apiStatus === "ok" ? "Available" : "Unavailable"}
                </span>
              </div>

              <div className="flex justify-between items-center pb-2 border-b border-border">
                <span className="text-zinc-300">Operational data</span>
                <span className={`px-2 py-0.5 rounded-base border text-[10px] font-bold ${stats.databaseStatus === "healthy" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-zinc-800 text-zinc-300 border-zinc-700"}`}>
                  {stats.databaseStatus === "healthy" ? "Available" : "Unknown"}
                </span>
              </div>

              <div className="flex justify-between items-center pb-2 border-b border-border">
                <span className="text-zinc-300">Discord connection</span>
                <span className={`px-2 py-0.5 rounded-base border text-[10px] font-bold ${stats.discordStatus === "connected" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-zinc-800 text-zinc-300 border-zinc-700"}`}>
                  {stats.discordStatus === "connected" ? "Connected" : "Not connected"}
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-zinc-300">Background sync</span>
                <span className={`px-2 py-0.5 rounded-base border text-[10px] font-bold ${stats.syncStatus === "healthy" ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-amber-950 text-amber-400 border-amber-800"}`}>
                  {stats.syncStatus === "healthy" ? "Running" : "Standby"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Action Items & Fork Health */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="border-b-2 border-border pb-3 bg-[#121216]">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              My Open Action Items
            </CardTitle>
          </CardHeader>

          <CardContent className="pt-4">
            <div className="space-y-2">
              {actionItems.length === 0 ? (
                <div className="text-xs text-zinc-400 font-mono">No pending action items.</div>
              ) : (
                actionItems.slice(0, 5).map((item) => (
                  <Link
                    key={item.id}
                    href="/dashboard/meetings"
                    className="flex justify-between items-center gap-4 rounded-base border border-border bg-[#181820] p-2.5 transition-colors hover:bg-white/5"
                  >
                    <span className="text-xs font-mono text-zinc-200 truncate">{item.task}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      {item.deadline ? (
                        <span className="text-[10px] font-mono text-zinc-400">{item.deadline}</span>
                      ) : null}
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 border border-border bg-black text-amber-400 rounded-base">
                        {item.status}
                      </span>
                    </span>
                  </Link>
                ))
              )}
              {actionItems.length > 0 && (
                <Link
                  href="/dashboard/meetings"
                  className="block pt-2 text-xs font-mono font-bold text-orange hover:underline"
                >
                  View all in Meetings &rarr;
                </Link>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="border-b-2 border-border pb-3 bg-[#121216]">
            <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
              Fork Chapter Health
            </CardTitle>
          </CardHeader>

          <CardContent className="pt-4">
            <div className="space-y-2.5 font-mono text-xs">
              {loading ? (
                <div className="text-xs text-zinc-400">Loading chapters...</div>
              ) : forks.length === 0 ? (
                <div className="text-xs text-zinc-400">No active forks registered.</div>
              ) : (
                forks.map((fork) => {
                  const score = fork.health_score ?? 100;
                  const isHealthy = score >= 70;
                  const isWarning = score >= 50 && score < 70;

                  return (
                    <div key={fork.id} className="flex justify-between items-center p-2.5 rounded-base border border-border bg-[#181820]">
                      <span className="font-bold text-zinc-200">{fork.city_name || fork.name}</span>
                      <span className={`px-2 py-0.5 rounded-base border text-[10px] font-bold ${isHealthy ? "bg-emerald-950 text-emerald-400 border-emerald-800" : isWarning ? "bg-amber-950 text-amber-400 border-amber-800" : "bg-red-950 text-red-400 border-red-800"}`}>
                        {score}/100
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions Card */}
      <Card className="border-2 border-border bg-[#141418] shadow-light">
        <CardHeader className="border-b-2 border-border pb-3 bg-[#121216]">
          <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">
            Quick Actions
          </CardTitle>
        </CardHeader>

        <CardContent className="pt-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <Dialog open={createForkOpen} onOpenChange={setCreateForkOpen}>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="flex items-center justify-center gap-2 px-4 py-2.5 font-heading font-black text-xs uppercase tracking-wider border-2 border-border bg-main text-white rounded-base shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
                >
                  <Plus className="size-4" />
                  Create Fork
                </button>
              </DialogTrigger>
              <DialogContent className="border-2 border-border bg-[#141418] text-white">
                <DialogHeader>
                  <DialogTitle className="font-heading font-black text-lg uppercase tracking-tight text-white">
                    Create New City Chapter Fork
                  </DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateFork} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="slug" className="font-mono text-xs text-zinc-300">Slug *</Label>
                    <Input id="slug" required value={forkForm.slug} onChange={(e) => setForkForm(prev => ({...prev, slug: e.target.value}))} placeholder="e.g. blr" className="border-2 border-border bg-black text-white font-mono" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="city_name" className="font-mono text-xs text-zinc-300">City Name *</Label>
                    <Input id="city_name" required value={forkForm.city_name} onChange={(e) => setForkForm(prev => ({...prev, city_name: e.target.value}))} placeholder="e.g. Bangalore" className="border-2 border-border bg-black text-white font-mono" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="discord_city_role_id" className="font-mono text-xs text-zinc-300">Discord City Role ID (optional)</Label>
                    <Input id="discord_city_role_id" value={forkForm.discord_city_role_id} onChange={(e) => setForkForm(prev => ({...prev, discord_city_role_id: e.target.value}))} placeholder="e.g. 1234567890" className="border-2 border-border bg-black text-white font-mono" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="discord_contributor_role_id" className="font-mono text-xs text-zinc-300">Discord Contributor Role ID (optional)</Label>
                    <Input id="discord_contributor_role_id" value={forkForm.discord_contributor_role_id} onChange={(e) => setForkForm(prev => ({...prev, discord_contributor_role_id: e.target.value}))} placeholder="e.g. 0987654321" className="border-2 border-border bg-black text-white font-mono" />
                  </div>
                  <button type="submit" className="w-full py-3 bg-orange text-black font-heading font-black text-xs uppercase tracking-wider rounded-base border-2 border-black shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all disabled:opacity-50" disabled={creatingFork}>
                    {creatingFork ? <Loader2 className="mx-auto size-4 animate-spin" /> : "Create Chapter"}
                  </button>
                </form>
              </DialogContent>
            </Dialog>

            <button
              type="button"
              onClick={handleRunSync}
              disabled={syncing}
              className="flex items-center justify-center gap-2 px-4 py-2.5 font-heading font-black text-xs uppercase tracking-wider border-2 border-border bg-[#181820] text-white rounded-base shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all disabled:opacity-50"
            >
              {syncing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4 text-orange" />}
              {syncing ? "Syncing..." : "Trigger Discord Sync"}
            </button>

            <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="flex items-center justify-center gap-2 px-4 py-2.5 font-heading font-black text-xs uppercase tracking-wider border-2 border-border bg-[#181820] text-white rounded-base shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
                >
                  <UserPlus className="size-4 text-emerald-400" />
                  Invite Contributor
                </button>
              </DialogTrigger>
              <DialogContent className="border-2 border-border bg-[#141418] text-white">
                <DialogHeader>
                  <DialogTitle className="font-heading font-black text-lg uppercase tracking-tight text-white">
                    Invite Member
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <p className="text-xs text-zinc-300 font-base">
                    Share this verified invite link with new contributors to join the bits&bytes community Discord server.
                  </p>
                  <div className="flex gap-2 items-center">
                    <Input readOnly value="https://discord.gg/bitsnbytes" className="flex-1 border-2 border-border bg-black text-white font-mono text-xs" />
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText("https://discord.gg/bitsnbytes");
                        setCopyFeedback(true);
                        setTimeout(() => setCopyFeedback(false), 2000);
                      }}
                      className="px-3 py-2 border-2 border-border bg-orange text-black font-mono font-bold text-xs rounded-base shadow-light hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                    >
                      {copyFeedback ? "Copied!" : <Copy className="size-4" />}
                    </button>
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
