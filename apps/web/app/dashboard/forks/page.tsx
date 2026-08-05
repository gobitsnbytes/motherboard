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

interface ForkOnboardingItem {
  fork_id: string;
  city_name: string;
  slug: string;
  stage: "submitted" | "in_review" | "compliance_check" | "approved" | "archived";
  is_active: boolean;
  health_score: number;
  compliance_summary: {
    passed_checks_count: number;
    total_checks_count: number;
  };
  track_leads_assigned_count: number;
  member_count: number;
  remedies_needed: string[];
}

export default function DashboardForksPage() {
  const [forks, setForks] = useState<ForkNode[]>([]);
  const [onboardingForks, setOnboardingForks] = useState<ForkOnboardingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingOnboarding, setLoadingOnboarding] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchForksData = async () => {
    setLoading(true);
    setLoadingOnboarding(true);
    setError(null);
    try {
      const data = await getForks();
      setForks(Array.isArray(data) ? data : []);

      const obRes = await fetch("/api/forks/onboarding");
      if (obRes.ok) {
        const obData = await obRes.json();
        setOnboardingForks(Array.isArray(obData) ? obData : []);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load Fork chapter network topology.");
    } finally {
      setLoading(false);
      setLoadingOnboarding(false);
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
                description="No fork chapters registered yet. Use the Create Fork action from the Overview dashboard to onboard a new chapter."
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

        {/* Right Column: Onboarding Pipeline */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <Zap className="size-5 text-[#97192C]" />
              <CardTitle className="font-heading font-bold text-base">Fork Onboarding Pipeline</CardTitle>
            </div>
            <Badge variant="neutral" className="border-border font-mono text-[10px]">
              Provisioning Engine
            </Badge>
          </CardHeader>
          <CardContent className="pt-4 space-y-3">
            {loadingOnboarding ? (
              <div className="space-y-3">
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            ) : onboardingForks.length === 0 ? (
              <EmptyState
                icon={<Zap className="size-8 text-muted-foreground" />}
                title="No forks in pipeline"
                description="Onboarding pipeline is clear."
              />
            ) : (
              onboardingForks.map((fork) => (
                <div
                  key={fork.fork_id}
                  className="flex flex-col gap-2 rounded-base border-2 border-border bg-[#111] p-3.5 text-white transition-all hover:translate-x-[2px] hover:translate-y-[2px]"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <MapPin className="size-4 text-[#FC920D]" />
                      <span className="font-heading font-bold text-sm text-white">
                        {fork.city_name}
                      </span>
                    </div>
                    <Badge
                      variant={
                        fork.stage === "approved" ? "success" :
                        fork.stage === "archived" ? "neutral" :
                        "warning"
                      }
                      className="capitalize text-[10px]"
                    >
                      {fork.stage.replace("_", " ")}
                    </Badge>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div className="text-[11px] text-muted-foreground">
                      <div className="flex items-center gap-1 mb-1">
                        <Activity className="size-3" />
                        Health: 
                        <span className={`font-bold ${fork.health_score >= 70 ? 'text-green-400' : fork.health_score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                          {fork.health_score}/100
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Users className="size-3" />
                        Members: {fork.member_count} ({fork.track_leads_assigned_count} leads)
                      </div>
                    </div>
                    <div className="text-[11px] text-muted-foreground text-right flex flex-col justify-end">
                      <div className="flex items-center justify-end gap-1">
                        <ShieldCheck className="size-3" />
                        <span className="font-bold text-white">{fork.compliance_summary.passed_checks_count}/{fork.compliance_summary.total_checks_count}</span> checks passed
                      </div>
                    </div>
                  </div>

                  {fork.remedies_needed && fork.remedies_needed.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/40">
                      <div className="text-[10px] font-bold text-yellow-400 mb-1 flex items-center gap-1">
                        <AlertTriangle className="size-3" />
                        Remedies Needed:
                      </div>
                      <ul className="list-disc list-inside text-[10px] text-muted-foreground space-y-1">
                        {fork.remedies_needed.map((remedy, idx) => (
                          <li key={idx} className="line-clamp-2">{remedy}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
