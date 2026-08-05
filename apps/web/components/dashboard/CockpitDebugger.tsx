"use client";

import React, { useState, useEffect } from "react";
import { X, Activity, Database, Shield, Cpu, Terminal, RefreshCw, Zap } from "lucide-react";
import { Badge, Button } from "@bnb/ui";
import { useSession } from "next-auth/react";

interface CockpitDebuggerProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CockpitDebugger({ isOpen, onClose }: CockpitDebuggerProps) {
  const { data: session } = useSession();
  const [latency, setLatency] = useState<number | null>(null);
  const [apiStatus, setApiStatus] = useState<string>("checking...");
  const [dbStatus, setDbStatus] = useState<string>("checking...");
  const [userProfile, setUserProfile] = useState<any>(null);
  const [hierarchy, setHierarchy] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const pingBackend = async () => {
    setRefreshing(true);
    const start = performance.now();
    try {
      const res = await fetch("/api/health/status");
      const end = performance.now();
      setLatency(Math.round(end - start));
      if (res.ok) {
        const data = await res.json();
        setApiStatus(data.database === "healthy" ? "Online (200 OK)" : "Degraded");
        setDbStatus(data.database);
      } else {
        setApiStatus(`HTTP ${res.status}`);
      }
    } catch (err) {
      setLatency(null);
      setApiStatus("Disconnected");
      setDbStatus("Offline");
    }

    try {
      const meRes = await fetch("/api/users/me");
      if (meRes.ok) {
        setUserProfile(await meRes.json());
      }
    } catch (e) {}

    try {
      const iamRes = await fetch("/api/iam/hierarchy");
      if (iamRes.ok) {
        setHierarchy(await iamRes.json());
      }
    } catch (e) {}

    setRefreshing(false);
  };

  useEffect(() => {
    if (isOpen) {
      pingBackend();
    }
  }, [isOpen]);

  // Keyboard shortcut Ctrl+Shift+D
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "d") {
        e.preventDefault();
        if (isOpen) onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-[#0a0a0c] border-l-2 border-border shadow-2xl flex flex-col font-mono text-xs text-foreground overflow-hidden animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b-2 border-border bg-[#121216]">
        <div className="flex items-center gap-2">
          <Terminal className="size-4 text-amber-400 animate-pulse" />
          <span className="font-heading font-bold text-sm tracking-wider uppercase text-amber-400">
            Stats for Nerds & Debugger
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="neutral"
            size="icon"
            onClick={pingBackend}
            disabled={refreshing}
            className="size-7"
          >
            <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
          <button
            type="button"
            onClick={onClose}
            className="flex size-7 items-center justify-center rounded-base border border-border text-foreground hover:bg-main hover:text-main-foreground"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* System Latency & Health */}
        <div className="rounded-base border border-border/80 bg-[#141418] p-3.5 space-y-2">
          <div className="flex items-center justify-between text-muted-foreground uppercase text-[10px] font-heading tracking-wider">
            <span className="flex items-center gap-1.5 text-foreground font-bold">
              <Activity className="size-3.5 text-emerald-400" />
              Runtime Telemetry
            </span>
            <Badge variant={latency && latency < 150 ? "success" : "warning"}>
              {latency !== null ? `${latency} ms` : "N/A"}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 text-[11px]">
            <div className="flex flex-col bg-black/40 p-2 rounded-sm border border-white/5">
              <span className="text-muted-foreground text-[10px]">API Latency</span>
              <span className="font-bold text-emerald-400">{latency ? `${latency}ms` : "Offline"}</span>
            </div>
            <div className="flex flex-col bg-black/40 p-2 rounded-sm border border-white/5">
              <span className="text-muted-foreground text-[10px]">API Status</span>
              <span className="font-bold text-foreground">{apiStatus}</span>
            </div>
            <div className="flex flex-col bg-black/40 p-2 rounded-sm border border-white/5">
              <span className="text-muted-foreground text-[10px]">Database Engine</span>
              <span className="font-bold text-blue-400">{dbStatus}</span>
            </div>
            <div className="flex flex-col bg-black/40 p-2 rounded-sm border border-white/5">
              <span className="text-muted-foreground text-[10px]">App Version</span>
              <span className="font-bold text-amber-400">v0.2.0-cockpit</span>
            </div>
          </div>
        </div>

        {/* User Identity & IAM Scopes */}
        <div className="rounded-base border border-border/80 bg-[#141418] p-3.5 space-y-2">
          <div className="flex items-center justify-between text-muted-foreground uppercase text-[10px] font-heading tracking-wider">
            <span className="flex items-center gap-1.5 text-foreground font-bold">
              <Shield className="size-3.5 text-amber-400" />
              Active IAM Identity
            </span>
            <Badge variant={userProfile?.is_super_admin ? "danger" : "neutral"}>
              {userProfile?.is_super_admin ? "Super Admin" : "Member"}
            </Badge>
          </div>

          <div className="space-y-1.5 pt-1 text-[11px]">
            <div className="flex justify-between border-b border-white/5 pb-1">
              <span className="text-muted-foreground">Internal User ID:</span>
              <span className="font-mono text-white/90 select-all truncate max-w-[200px]">
                {session?.user?.internalUserId || userProfile?.id || "Unset"}
              </span>
            </div>
            <div className="flex justify-between border-b border-white/5 pb-1">
              <span className="text-muted-foreground">Discord Snowflake:</span>
              <span className="font-mono text-white/90">
                {session?.user?.discordId || "N/A"}
              </span>
            </div>
            <div className="flex justify-between border-b border-white/5 pb-1">
              <span className="text-muted-foreground">Display Name:</span>
              <span className="text-white/90 font-bold">
                {userProfile?.display_name || session?.user?.name || "Anonymous"}
              </span>
            </div>
            <div className="flex justify-between pb-1">
              <span className="text-muted-foreground">Profile Completed:</span>
              <span className={userProfile?.profile_completed ? "text-emerald-400" : "text-amber-400"}>
                {userProfile?.profile_completed ? "Yes (100%)" : "Setup Required"}
              </span>
            </div>
          </div>
        </div>

        {/* IAM Hierarchy Metrics */}
        {hierarchy && (
          <div className="rounded-base border border-border/80 bg-[#141418] p-3.5 space-y-2">
            <div className="flex items-center justify-between text-muted-foreground uppercase text-[10px] font-heading tracking-wider">
              <span className="flex items-center gap-1.5 text-foreground font-bold">
                <Database className="size-3.5 text-blue-400" />
                IAM Policy Graph
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
              <div className="bg-black/40 p-2 rounded-sm border border-white/5">
                <span className="text-muted-foreground text-[10px]">Total Groups</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_groups}</p>
              </div>
              <div className="bg-black/40 p-2 rounded-sm border border-white/5">
                <span className="text-muted-foreground text-[10px]">Granted Policies</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_grants}</p>
              </div>
              <div className="bg-black/40 p-2 rounded-sm border border-white/5">
                <span className="text-muted-foreground text-[10px]">Role Mappings</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_mappings}</p>
              </div>
              <div className="bg-black/40 p-2 rounded-sm border border-white/5">
                <span className="text-muted-foreground text-[10px]">Active Memberships</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_memberships}</p>
              </div>
            </div>
          </div>
        )}

        {/* AI Agent Telemetry */}
        <div className="rounded-base border border-border/80 bg-[#141418] p-3.5 space-y-2">
          <div className="flex items-center justify-between text-muted-foreground uppercase text-[10px] font-heading tracking-wider">
            <span className="flex items-center gap-1.5 text-foreground font-bold">
              <Cpu className="size-3.5 text-purple-400" />
              AI Agent Engine
            </span>
            <Badge variant="success">Gemini 3.5 Flash</Badge>
          </div>
          <div className="space-y-1 pt-1 text-[11px]">
            <div className="flex justify-between border-b border-white/5 pb-1">
              <span className="text-muted-foreground">Active Agents:</span>
              <span className="font-bold text-purple-300">Contract Assistant, Dyslexic Sourcing</span>
            </div>
            <div className="flex justify-between border-b border-white/5 pb-1">
              <span className="text-muted-foreground">Token Efficiency:</span>
              <span className="text-emerald-400 font-mono">60% cached</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Model Context:</span>
              <span className="font-mono text-white/90">1.0M tokens</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer shortcut tip */}
      <div className="p-3 border-t-2 border-border bg-[#121216] text-[10px] text-muted-foreground text-center">
        Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 text-white font-mono">Ctrl+Shift+D</kbd> to toggle Cockpit Debugger
      </div>
    </div>
  );
}
