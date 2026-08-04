"use client";

import React, { useEffect, useState } from "react";
import {
  GitBranch,
  MapPin,
  Users,
  Activity,
  Plus,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Zap,
  ExternalLink,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
  Skeleton,
} from "@bnb/ui";
import EmptyState from "components/dashboard/EmptyState";
import { getForks } from "lib/dashboard";

interface ForkNode {
  id: string;
  city_name: string;
  lead_name?: string;
  status: "active" | "warning" | "stale" | "pending";
  health_score?: number;
  last_pulse_at?: string;
  onboarding_step?: number;
  member_count?: number;
}

export default function DashboardForksPage() {
  const [forks, setForks] = useState<ForkNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchForksData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getForks();
      setForks(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setError("Failed to load Fork chapter network topology.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForksData();
  }, []);

  const activeForks = forks.filter((f) => f.status === "active" || !f.status);
  const warningForks = forks.filter((f) => f.status === "warning");
  const staleForks = forks.filter((f) => f.status === "stale");

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-base border-2 border-border bg-[#97192C] p-6 text-white shadow-shadow">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="size-6 text-[#FC920D]" />
            <h1 className="font-heading font-extrabold text-2xl tracking-wide">
              Fork Chapter Network Topology
            </h1>
          </div>
          <p className="mt-1 text-xs text-white/80 font-base">
            Local chapter lifecycle, weekly `/pulse` tracking, 0-100 health scoring, and automated archiving.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={fetchForksData}
            variant="neutral"
            className="border-2 border-border bg-[#111] text-white hover:bg-[#222]"
          >
            <RefreshCw className={`size-4 mr-1.5 ${loading ? "animate-spin text-[#FC920D]" : ""}`} />
            Refresh Network
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-base border-2 border-[#97192C] bg-[#97192C]/10 p-4 text-xs font-bold text-red-200 shadow-shadow">
          <AlertTriangle className="size-5 shrink-0 text-[#97192C]" />
          <span>{error}</span>
        </div>
      )}

      {/* Quick Stats Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Total Fork Nodes
            </CardTitle>
            <GitBranch className="size-4 text-[#FC920D]" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {forks.length}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Recognized operating chapters</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Active Chapter Pulse
            </CardTitle>
            <Activity className="size-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {activeForks.length}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Submitted `/pulse` &lt; 60 days</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Stale Archival Alerts
            </CardTitle>
            <AlertTriangle className="size-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {warningForks.length + staleForks.length}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">60-89d warning / 90d+ archive</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Governance Model
            </CardTitle>
            <ShieldCheck className="size-4 text-[#97192C]" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="warning">Teen-Led Required</Badge>
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">Upstream Board legal approval</p>
          </CardContent>
        </Card>
      </div>

      {/* Responsive 2-Column Main Section */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left Column: Active Chapters */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <MapPin className="size-5 text-[#FC920D]" />
              <CardTitle className="font-heading font-bold text-base">Active City Chapters</CardTitle>
            </div>
            <Badge variant="neutral" className="border-border font-mono text-[10px]">
              Notion Registry Sync
            </Badge>
          </CardHeader>
          <CardContent className="pt-4">
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : forks.length === 0 ? (
              <EmptyState
                icon={<GitBranch className="size-8 text-muted-foreground" />}
                title="No active Fork nodes registered"
                description="Use /admin-add-lead or /merge via Discord bot to onboard new local chapters."
              />
            ) : (
              <div className="space-y-3">
                {forks.map((fork) => (
                  <div
                    key={fork.id}
                    className="flex items-center justify-between rounded-base border-2 border-border bg-[#111] p-3.5 text-white transition-all hover:translate-x-[2px] hover:translate-y-[2px]"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <MapPin className="size-4 text-[#FC920D]" />
                        <span className="font-heading font-bold text-sm text-white">
                          {fork.city_name}
                        </span>
                      </div>
                      <div className="text-[11px] text-muted-foreground mt-1">
                        Lead: {fork.lead_name || "Unassigned"} &bull; {fork.member_count ?? 1} builders
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-heading font-bold text-sm text-green-400">
                        Score: {fork.health_score ?? 100}/100
                      </div>
                      <Badge variant="success" className="mt-1">
                        {fork.status || "Active"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: 7-Step Onboarding Checklist */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <Zap className="size-5 text-[#97192C]" />
              <CardTitle className="font-heading font-bold text-base">7-Step Onboarding Pipeline</CardTitle>
            </div>
            <Badge variant="neutral" className="border-border font-mono text-[10px]">
              Provisioning Engine
            </Badge>
          </CardHeader>
          <CardContent className="pt-4 space-y-2.5">
            {[
              { step: 1, name: "Accept GitHub Organization Invite", desc: "Access code repositories and templates" },
              { step: 2, name: "Join Leads Council Discord", desc: "Access private operational channels" },
              { step: 3, name: "Setup [city]@gobitsnbytes.org Email", desc: "Configure official chapter email handle" },
              { step: 4, name: "Deploy Chapter Website Landing Page", desc: "Set up regional showcase page" },
              { step: 5, name: "Connect Notion Database Workspace", desc: "Sync local events and attendees upstream" },
              { step: 6, name: "Execute Initial `/pulse` Command", desc: "Establish weekly chapter activity metric" },
              { step: 7, name: "Register Team & Outline First Event", desc: "Publish event pipeline to Cal.com sync" },
            ].map((item) => (
              <div
                key={item.step}
                className="flex items-center gap-3 rounded-base border border-border/60 bg-[#121212] p-2.5 text-xs text-foreground"
              >
                <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#97192C] font-heading font-bold text-[11px] text-white">
                  {item.step}
                </div>
                <div>
                  <div className="font-heading font-bold text-white text-xs">{item.name}</div>
                  <div className="text-[10px] text-muted-foreground">{item.desc}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
