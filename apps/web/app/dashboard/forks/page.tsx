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
import ForkOnboardingModal from "components/dashboard/ForkOnboardingModal";
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
  const [selectedForkId, setSelectedForkId] = useState<string | null>(null);

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
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-base border-2 border-border bg-main p-5 text-main-foreground shadow-dark">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="size-6 text-orange" />
            <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight uppercase">
              Fork Chapter Network
            </h1>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-main-foreground/80 font-base">
            Local chapter lifecycle, weekly `/pulse` tracking, 0-100 health scoring, and automated archiving.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchForksData}
            className="flex items-center gap-1.5 px-4 py-2 font-mono font-bold text-xs uppercase rounded-base border-2 border-border bg-secondary-background text-foreground hover:bg-orange hover:text-black shadow-light hover:translate-x-[1px] hover:translate-y-[1px] transition-all"
          >
            <RefreshCw className={`size-3.5 mr-1 ${loading ? "animate-spin text-orange" : "text-orange"}`} />
            Refresh Network
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-base border-2 border-red-700 bg-red-50 p-4 text-xs font-mono font-bold text-red-900 shadow-light">
          <AlertTriangle className="size-5 shrink-0 text-red-700" />
          <span>{error}</span>
        </div>
      )}

      {/* Quick Stats Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Total Fork Nodes
            </CardTitle>
            <GitBranch className="size-4 text-orange" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {forks.length}
              </div>
            )}
            <p className="text-[11px] font-mono text-muted-foreground mt-1">Recognized operating chapters</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Active Chapter Pulse
            </CardTitle>
            <Activity className="size-4 text-emerald-400" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {activeForks.length}
              </div>
            )}
            <p className="text-[11px] font-mono text-muted-foreground mt-1">Submitted `/pulse` &lt; 60 days</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Stale Archival Alerts
            </CardTitle>
            <AlertTriangle className="size-4 text-amber-400" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {warningForks.length + staleForks.length}
              </div>
            )}
            <p className="text-[11px] font-mono text-muted-foreground mt-1">60-89d warning / 90d+ archive</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Governance Model
            </CardTitle>
            <ShieldCheck className="size-4 text-orange" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 mt-1">
              <span className="border-2 border-border bg-main text-white px-2 py-0.5 text-[10px] font-mono font-bold rounded-base shadow-light">
                Teen-Led Required
              </span>
            </div>
            <p className="text-[11px] font-mono text-muted-foreground mt-2">Upstream Board legal approval</p>
          </CardContent>
        </Card>
      </div>

      {/* Responsive 2-Column Main Section */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left Column: Active Chapters */}
        <Card className="border-2 border-border bg-secondary-background shadow-dark rounded-base">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border bg-muted pb-3.5">
            <div className="flex items-center gap-2">
              <MapPin className="size-4 text-orange" />
              <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-foreground">Active City Chapters</CardTitle>
            </div>
            <span className="border border-border bg-secondary-background text-muted-foreground font-mono text-[10px] px-2 py-0.5 rounded-base">
              Notion Registry Sync
            </span>
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
                icon={<GitBranch className="size-8 text-zinc-600" />}
                title="No active Fork nodes registered"
                description="No fork chapters registered yet. Use the Create Fork action from the Overview dashboard to onboard a new chapter."
              />
            ) : (
              <div className="space-y-3">
                {forks.map((fork) => (
                  <div
                    key={fork.id}
                    className="flex items-center justify-between rounded-base border-2 border-border bg-secondary-background p-3.5 text-foreground transition-all hover:translate-x-[2px] hover:translate-y-[2px] shadow-light"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <MapPin className="size-4 text-orange" />
                        <span className="font-heading font-black text-sm text-foreground uppercase">
                          {fork.city_name}
                        </span>
                      </div>
                      <div className="text-[11px] font-mono text-muted-foreground mt-1">
                        Lead: {fork.lead_name || "Unassigned"} &bull; {fork.member_count ?? 1} builders
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold text-xs text-emerald-400">
                        Score: {fork.health_score ?? 100}/100
                      </div>
                      <span className="inline-block mt-1 px-2 py-0.5 text-[10px] font-mono font-bold rounded-base border border-emerald-800 bg-emerald-950 text-emerald-400">
                        {fork.status || "Active"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: Onboarding Pipeline */}
        <Card className="border-2 border-border bg-secondary-background shadow-dark rounded-base">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border bg-muted pb-3.5">
            <div className="flex items-center gap-2">
              <Zap className="size-4 text-orange" />
              <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-foreground">Fork Onboarding Pipeline</CardTitle>
            </div>
            <span className="border border-border bg-secondary-background text-muted-foreground font-mono text-[10px] px-2 py-0.5 rounded-base">
              Provisioning Engine
            </span>
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
                icon={<Zap className="size-8 text-zinc-600" />}
                title="No forks in pipeline"
                description="Onboarding pipeline is clear."
              />
            ) : (
              onboardingForks.map((fork) => (
                <button
                  type="button"
                  key={fork.fork_id}
                  onClick={() => setSelectedForkId(fork.fork_id)}
                  className="flex w-full flex-col gap-2 rounded-base border-2 border-border bg-secondary-background p-3.5 text-left text-foreground transition-all hover:translate-x-[2px] hover:translate-y-[2px] shadow-light"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <MapPin className="size-4 text-orange" />
                      <span className="font-heading font-black text-sm text-foreground uppercase">
                        {fork.city_name}
                      </span>
                    </div>
                    <span
                      className={`px-2 py-0.5 font-mono text-[10px] font-bold rounded-base border ${
                        fork.stage === "approved" ? "bg-emerald-950 text-emerald-400 border-emerald-800" :
                        fork.stage === "archived" ? "bg-zinc-800 text-zinc-400 border-zinc-700" :
                        "bg-amber-950 text-amber-400 border-amber-800"
                      }`}
                    >
                      {fork.stage.replace("_", " ")}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div className="text-[11px] font-mono text-muted-foreground">
                      <div className="flex items-center gap-1 mb-1">
                        <Activity className="size-3 text-orange" />
                        Health: 
                        <span className={`font-bold ${fork.health_score >= 70 ? 'text-emerald-400' : fork.health_score >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
                          {fork.health_score}/100
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Users className="size-3 text-muted-foreground" />
                        Members: {fork.member_count} ({fork.track_leads_assigned_count} leads)
                      </div>
                    </div>
                    <div className="text-[11px] font-mono text-zinc-400 text-right flex flex-col justify-end">
                      <div className="flex items-center justify-end gap-1 text-muted-foreground">
                        <ShieldCheck className="size-3 text-emerald-400" />
                        <span className="font-bold text-foreground">{fork.compliance_summary.passed_checks_count}/{fork.compliance_summary.total_checks_count}</span> checks passed
                      </div>
                    </div>
                  </div>

                  {fork.remedies_needed && fork.remedies_needed.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border">
                      <div className="text-[10px] font-mono font-bold text-amber-400 mb-1 flex items-center gap-1">
                        <AlertTriangle className="size-3" />
                        Remedies Needed:
                      </div>
                      <ul className="list-disc list-inside text-[10px] font-mono text-zinc-400 space-y-1">
                        {fork.remedies_needed.map((remedy, idx) => (
                          <li key={idx} className="line-clamp-2">{remedy}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </button>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <ForkOnboardingModal
        forkId={selectedForkId}
        onClose={() => setSelectedForkId(null)}
        onChanged={() => { void fetchForksData(); }}
      />
    </div>
  );
}
