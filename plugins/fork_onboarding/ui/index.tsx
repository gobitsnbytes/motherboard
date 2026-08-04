"use client";

import React, { useEffect, useState } from "react";
import { GitFork, RefreshCw, CheckCircle2, ShieldCheck, Activity, UserCheck, Plus, AlertCircle } from "lucide-react";

interface Application {
  id: str;
  city: string;
  lead_name: string;
  lead_email: string;
  discord_user_id: string;
  repo_url: string;
  team_size: number;
  status: string;
  compliance_status: string;
  compliance_checks: Record<string, boolean>;
  health_score: number;
  metrics: Record<string, number>;
  roles_provisioned: string[];
}

interface Stats {
  total_applications: number;
  approved_forks: number;
  pending_audit: number;
  avg_health_score: number;
  total_roles_provisioned: number;
}

export default function ForkOnboardingUI() {
  const [apps, setApps] = useState<Application[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    city: "",
    lead_name: "",
    lead_email: "",
    discord_user_id: "",
    repo_url: "",
    team_size: 4,
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [appsRes, statsRes] = await Promise.all([
        fetch("/api/plugins/fork_onboarding/applications"),
        fetch("/api/plugins/fork_onboarding/stats"),
      ]);
      if (appsRes.ok) {
        const appsData = await appsRes.json();
        setApps(appsData);
      }
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (err) {
      console.error("Failed to fetch fork onboarding data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateApp = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading("create");
    try {
      const res = await fetch("/api/plugins/fork_onboarding/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        setShowModal(false);
        setForm({ city: "", lead_name: "", lead_email: "", discord_user_id: "", repo_url: "", team_size: 4 });
        await fetchData();
      }
    } catch (err) {
      console.error("Error creating application", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAudit = async (id: string) => {
    setActionLoading(`audit-${id}`);
    try {
      const res = await fetch(`/api/plugins/fork_onboarding/applications/${id}/audit`, { method: "POST" });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error("Audit error", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleScore = async (id: string) => {
    setActionLoading(`score-${id}`);
    try {
      const res = await fetch(`/api/plugins/fork_onboarding/applications/${id}/score`, { method: "POST" });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error("Score error", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleProvision = async (id: string) => {
    setActionLoading(`provision-${id}`);
    try {
      const res = await fetch(`/api/plugins/fork_onboarding/applications/${id}/provision-roles`, { method: "POST" });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error("Provision error", err);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 border-4 border-border bg-main/5 rounded-base shadow-light">
      {/* Top Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center p-3 border-2 border-border bg-main rounded-base text-main-foreground shadow-light">
            <GitFork className="size-6" />
          </div>
          <div>
            <h2 className="text-xl font-heading font-bold text-foreground">
              Fork Onboarding & Compliance Engine
            </h2>
            <p className="text-xs text-muted-foreground font-base mt-0.5">
              Intake pipeline, statutory compliance audits, 0-100 health scoring, & Discord role provisioning.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 border-2 border-border bg-bg text-foreground px-3.5 py-2 text-xs font-bold rounded-base hover:bg-main/10 transition-all"
          >
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 border-2 border-border bg-main text-main-foreground px-4 py-2 text-xs font-bold rounded-base hover:bg-main/90 shadow-light transition-all hover:translate-x-[2px] hover:translate-y-[2px]"
          >
            <Plus className="size-4" />
            Submit Application
          </button>
        </div>
      </div>

      {/* Stats Section */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Total Intake</span>
            <GitFork className="size-4 text-main" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2">
            {stats ? stats.total_applications : "-"}
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Approved Forks</span>
            <CheckCircle2 className="size-4 text-green-500" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2">
            {stats ? stats.approved_forks : "-"}
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Average Health</span>
            <Activity className="size-4 text-amber-500" />
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-3xl font-heading font-extrabold text-foreground">
              {stats ? `${stats.avg_health_score}/100` : "-"}
            </span>
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Roles Provisioned</span>
            <UserCheck className="size-4 text-blue-500" />
          </div>
          <div className="text-3xl font-heading font-extrabold text-foreground mt-2">
            {stats ? stats.total_roles_provisioned : "-"}
          </div>
        </div>
      </div>

      {/* Applications Table */}
      <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light overflow-x-auto">
        <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider mb-4">
          Fork Onboarding Pipeline
        </h3>

        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b-2 border-border bg-main/10 font-heading text-foreground">
              <th className="p-3">Fork / City</th>
              <th className="p-3">Lead Details</th>
              <th className="p-3">Compliance</th>
              <th className="p-3">Health Score</th>
              <th className="p-3">Status</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {apps.map((app) => (
              <tr key={app.id} className="border-b border-border/50 hover:bg-main/5 transition-colors">
                <td className="p-3 font-bold font-mono">
                  <div className="text-sm font-bold text-foreground">{app.city}</div>
                  <div className="text-[10px] text-muted-foreground">{app.id}</div>
                </td>
                <td className="p-3">
                  <div className="font-bold text-foreground">{app.lead_name}</div>
                  <div className="text-[10px] text-muted-foreground">{app.lead_email}</div>
                  <div className="text-[10px] font-mono text-muted-foreground">Discord: {app.discord_user_id}</div>
                </td>
                <td className="p-3">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-base font-bold text-[10px] border-2 border-border ${
                      app.compliance_status === "COMPLIANT"
                        ? "bg-green-500/20 text-green-700"
                        : "bg-amber-500/20 text-amber-700"
                    }`}
                  >
                    <ShieldCheck className="size-3" />
                    {app.compliance_status}
                  </span>
                </td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-main/20 h-2 rounded-full overflow-hidden border border-border">
                      <div
                        className={`h-full ${
                          app.health_score >= 80
                            ? "bg-green-500"
                            : app.health_score >= 60
                            ? "bg-amber-500"
                            : "bg-red-500"
                        }`}
                        style={{ width: `${app.health_score}%` }}
                      />
                    </div>
                    <span className="font-bold text-foreground font-mono">{app.health_score}/100</span>
                  </div>
                </td>
                <td className="p-3">
                  <span className="px-2 py-0.5 rounded-base font-bold text-[10px] border border-border bg-bg text-foreground">
                    {app.status}
                  </span>
                </td>
                <td className="p-3 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <button
                      onClick={() => handleAudit(app.id)}
                      disabled={actionLoading === `audit-${app.id}`}
                      className="px-2 py-1 text-[10px] font-bold border-2 border-border bg-bg hover:bg-main/20 rounded-base"
                    >
                      Audit
                    </button>
                    <button
                      onClick={() => handleScore(app.id)}
                      disabled={actionLoading === `score-${app.id}`}
                      className="px-2 py-1 text-[10px] font-bold border-2 border-border bg-amber-400 text-black rounded-base"
                    >
                      Score
                    </button>
                    <button
                      onClick={() => handleProvision(app.id)}
                      disabled={actionLoading === `provision-${app.id}`}
                      className="px-2 py-1 text-[10px] font-bold border-2 border-border bg-main text-main-foreground rounded-base"
                    >
                      Provision
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Submit Application Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="border-4 border-border bg-bg p-6 rounded-base shadow-light w-full max-w-md">
            <h3 className="text-lg font-heading font-bold text-foreground mb-4">Submit Fork Intake Application</h3>
            <form onSubmit={handleCreateApp} className="flex flex-col gap-3 text-xs">
              <div>
                <label className="font-bold block mb-1">City Name</label>
                <input
                  required
                  type="text"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  placeholder="e.g. Prayagraj"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Fork Lead Full Name</label>
                <input
                  required
                  type="text"
                  value={form.lead_name}
                  onChange={(e) => setForm({ ...form, lead_name: e.target.value })}
                  placeholder="Lead Name"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Lead Email</label>
                <input
                  required
                  type="email"
                  value={form.lead_email}
                  onChange={(e) => setForm({ ...form, lead_email: e.target.value })}
                  placeholder="lead@gobitsnbytes.org"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Discord User ID</label>
                <input
                  required
                  type="text"
                  value={form.discord_user_id}
                  onChange={(e) => setForm({ ...form, discord_user_id: e.target.value })}
                  placeholder="18-digit Discord Snowflake"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">GitHub Repo URL</label>
                <input
                  required
                  type="url"
                  value={form.repo_url}
                  onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
                  placeholder="https://github.com/gobitsnbytes/fork-city"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border-2 border-border bg-bg font-bold rounded-base"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === "create"}
                  className="px-4 py-2 border-2 border-border bg-main text-main-foreground font-bold rounded-base"
                >
                  Submit Application
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
