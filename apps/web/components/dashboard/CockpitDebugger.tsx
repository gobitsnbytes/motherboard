"use client";

import React, { useState, useEffect } from "react";
import { X, Activity, Database, Shield, Cpu, Terminal, RefreshCw, Zap } from "lucide-react";
import { Badge, Button } from "@bnb/ui";
import { useSession } from "next-auth/react";
import { APP_VERSION_LABEL } from "../../lib/version";

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
        <div className="rounded-base border-2 border-border bg-[#141418] p-3.5 space-y-2 shadow-light">
          <div className="flex items-center justify-between text-zinc-400 uppercase text-[10px] font-mono font-bold tracking-wider">
            <span className="flex items-center gap-1.5 text-white font-bold">
              <Activity className="size-3.5 text-emerald-400" />
              Runtime Telemetry
            </span>
            <span className={`px-2 py-0.5 rounded-base text-[10px] font-mono font-bold border ${latency && latency < 150 ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-amber-950 text-amber-400 border-amber-800"}`}>
              {latency !== null ? `${latency} ms` : "N/A"}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 text-[11px] font-mono">
            <div className="flex flex-col bg-black p-2 rounded-base border border-border">
              <span className="text-zinc-500 text-[10px]">API Latency</span>
              <span className="font-bold text-emerald-400">{latency ? `${latency}ms` : "Offline"}</span>
            </div>
            <div className="flex flex-col bg-black p-2 rounded-base border border-border">
              <span className="text-zinc-500 text-[10px]">API Status</span>
              <span className="font-bold text-white">{apiStatus}</span>
            </div>
            <div className="flex flex-col bg-black p-2 rounded-base border border-border">
              <span className="text-zinc-500 text-[10px]">Database Engine</span>
              <span className="font-bold text-orange">{dbStatus}</span>
            </div>
            <div className="flex flex-col bg-black p-2 rounded-base border border-border">
              <span className="text-zinc-500 text-[10px]">App Version</span>
              <span className="font-bold text-amber-400">{APP_VERSION_LABEL}-cockpit</span>
            </div>
          </div>
        </div>

        {/* User Identity & IAM Scopes */}
        <div className="rounded-base border-2 border-border bg-[#141418] p-3.5 space-y-2 shadow-light">
          <div className="flex items-center justify-between text-zinc-400 uppercase text-[10px] font-mono font-bold tracking-wider">
            <span className="flex items-center gap-1.5 text-white font-bold">
              <Shield className="size-3.5 text-orange" />
              Active IAM Identity
            </span>
            <span className={`px-2 py-0.5 rounded-base text-[10px] font-mono font-bold border ${userProfile?.is_super_admin ? "bg-orange text-black border-black shadow-light" : "bg-[#181820] text-zinc-300 border-border"}`}>
              {userProfile?.is_super_admin ? "Super Admin" : "Member"}
            </span>
          </div>

          <div className="space-y-1.5 pt-1 text-[11px] font-mono">
            <div className="flex justify-between border-b border-border/50 pb-1">
              <span className="text-zinc-400">Internal User ID:</span>
              <span className="text-zinc-200 select-all truncate max-w-[200px]">
                {session?.user?.internalUserId || userProfile?.id || "Unset"}
              </span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-1">
              <span className="text-zinc-400">Discord Snowflake:</span>
              <span className="text-zinc-200">
                {session?.user?.discordId || "N/A"}
              </span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-1">
              <span className="text-zinc-400">Display Name:</span>
              <span className="text-white font-bold">
                {userProfile?.display_name || session?.user?.name || "Anonymous"}
              </span>
            </div>
            <div className="flex justify-between pb-1">
              <span className="text-zinc-400">Profile Completed:</span>
              <span className={userProfile?.profile_completed ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                {userProfile?.profile_completed ? "Yes (100%)" : "Setup Required"}
              </span>
            </div>
          </div>
        </div>

        {/* IAM Hierarchy Metrics */}
        {hierarchy && (
          <div className="rounded-base border-2 border-border bg-[#141418] p-3.5 space-y-2 shadow-light">
            <div className="flex items-center justify-between text-zinc-400 uppercase text-[10px] font-mono font-bold tracking-wider">
              <span className="flex items-center gap-1.5 text-white font-bold">
                <Database className="size-3.5 text-orange" />
                IAM Policy Graph
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 font-mono">
              <div className="bg-black p-2 rounded-base border border-border">
                <span className="text-zinc-500 text-[10px]">Total Groups</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_groups}</p>
              </div>
              <div className="bg-black p-2 rounded-base border border-border">
                <span className="text-zinc-500 text-[10px]">Granted Policies</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_grants}</p>
              </div>
              <div className="bg-black p-2 rounded-base border border-border">
                <span className="text-zinc-500 text-[10px]">Role Mappings</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_mappings}</p>
              </div>
              <div className="bg-black p-2 rounded-base border border-border">
                <span className="text-zinc-500 text-[10px]">Active Memberships</span>
                <p className="font-bold text-lg text-white">{hierarchy.total_memberships}</p>
              </div>
            </div>
          </div>
        )}

        {/* AI Agent Telemetry */}
        <div className="rounded-base border-2 border-border bg-[#141418] p-3.5 space-y-2 shadow-light">
          <div className="flex items-center justify-between text-zinc-400 uppercase text-[10px] font-mono font-bold tracking-wider">
            <span className="flex items-center gap-1.5 text-white font-bold">
              <Cpu className="size-3.5 text-orange" />
              AI Agent Engine
            </span>
            <span className="px-2 py-0.5 rounded-base text-[10px] font-mono font-bold border border-emerald-800 bg-emerald-950 text-emerald-400">
              Gemini 3.5 Flash
            </span>
          </div>
          <div className="space-y-1.5 pt-1 text-[11px] font-mono">
            <div className="flex justify-between border-b border-border/50 pb-1">
              <span className="text-zinc-400">Active Agents:</span>
              <span className="font-bold text-orange">Contract &amp; Dyslexic</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-1">
              <span className="text-zinc-400">Token Efficiency:</span>
              <span className="text-emerald-400 font-mono">60% cached</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Model Context:</span>
              <span className="text-zinc-200">1.0M tokens</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer shortcut tip */}
      <div className="p-3 border-t-2 border-border bg-[#121216] text-[10px] font-mono text-zinc-400 text-center">
        Press <kbd className="px-1.5 py-0.5 rounded-base border border-border bg-black text-white font-mono">Ctrl+Shift+D</kbd> to toggle Cockpit Debugger
      </div>
    </div>
  );
}
