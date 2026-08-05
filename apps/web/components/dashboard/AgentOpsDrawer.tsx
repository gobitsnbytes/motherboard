"use client";

import React, { useState } from "react";
import { Bot, Play, CheckCircle2, Clock, Terminal, Zap, ShieldAlert, Sparkles, RefreshCw, X } from "lucide-react";
import { Badge, Button, Input } from "@bnb/ui";

interface AgentOpsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AgentOpsDrawer({ isOpen, onClose }: AgentOpsDrawerProps) {
  const [agents, setAgents] = useState([
    {
      id: "contract-assistant",
      name: "Contract & Signature Assistant",
      status: "idle",
      lastRun: "10 mins ago",
      description: "Generates Section 8 compliant contracts and audits signature hashes.",
      tokensUsed: 4250,
    },
    {
      id: "dyslexic-sourcing",
      name: "Dyslexic Sponsorship Sourcing",
      status: "running",
      lastRun: "Active now",
      description: "Crawls web & LinkedIn for potential tech sponsors & partners.",
      tokensUsed: 18400,
    },
    {
      id: "notion-sync-agent",
      name: "Notion Fork Lifecycle Sync",
      status: "idle",
      lastRun: "1 hour ago",
      description: "Bidirectional sync between local SQL DB and Notion Workspace.",
      tokensUsed: 8900,
    },
    {
      id: "chrono-v2-agent",
      name: "Chrono v2 Team Meeting Scheduler",
      status: "idle",
      lastRun: "3 hours ago",
      description: "Matches availability windows across team profiles and Discord roles.",
      tokensUsed: 3100,
    },
  ]);

  const [promptInput, setPromptInput] = useState("");
  const [logs, setLogs] = useState<string[]>([
    "[00:14:02] [SYSTEM] Agent Engine initialized with Gemini 3.5 Flash",
    "[00:14:05] [NOTION_SYNC] Fork registry database synced successfully (8 cities)",
    "[00:15:12] [DYSLEXIC] Sourced 3 new tech sponsor leads for Lucknow Build Guild",
  ]);
  const [isExecuting, setIsExecuting] = useState(false);

  const handleRunAgent = (agentId: string) => {
    setAgents((prev) =>
      prev.map((a) => (a.id === agentId ? { ...a, status: "running" } : a))
    );
    setLogs((prev) => [
      `[${new Date().toLocaleTimeString()}] [${agentId.toUpperCase()}] Triggered manual agent run...`,
      ...prev,
    ]);

    setTimeout(() => {
      setAgents((prev) =>
        prev.map((a) => (a.id === agentId ? { ...a, status: "idle", lastRun: "Just now" } : a))
      );
      setLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] [${agentId.toUpperCase()}] Agent task completed cleanly. Output verified.`,
        ...prev,
      ]);
    }, 2500);
  };

  const handlePromptSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptInput.trim()) return;

    const input = promptInput;
    setPromptInput("");
    setIsExecuting(true);
    setLogs((prev) => [`[${new Date().toLocaleTimeString()}] [USER] Prompt submitted: "${input}"`, ...prev]);

    setTimeout(() => {
      setIsExecuting(false);
      setLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] [AI_COPILOT] Query processed. Analyzed 100 member profiles and 8 fork nodes.`,
        ...prev,
      ]);
    }, 1800);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-[#0a0a0c] border-l-2 border-border shadow-2xl flex flex-col font-body text-xs text-foreground overflow-hidden animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b-2 border-border bg-[#121216]">
        <div className="flex items-center gap-2">
          <Bot className="size-4 text-purple-400 animate-pulse" />
          <span className="font-heading font-bold text-sm tracking-wider uppercase text-purple-400">
            AI Agent Ops & Copilot
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex size-7 items-center justify-center rounded-base border border-border text-foreground hover:bg-main hover:text-main-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Quick Agent Actions */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-muted-foreground uppercase text-[10px] font-heading tracking-wider">
            <span className="flex items-center gap-1.5 text-foreground font-bold">
              <Zap className="size-3.5 text-amber-400" />
              Active Autonomous Agents
            </span>
            <Badge variant="neutral">{agents.length} Registered</Badge>
          </div>

          <div className="space-y-2 pt-1">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="rounded-base border border-border/80 bg-[#141418] p-3 flex flex-col gap-2 transition-all hover:border-purple-500/40"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-heading font-bold text-sm text-foreground flex items-center gap-2">
                      {agent.name}
                      {agent.status === "running" && (
                        <span className="flex size-2 rounded-full bg-purple-400 animate-ping" />
                      )}
                    </h4>
                    <p className="text-[11px] text-muted-foreground mt-0.5">{agent.description}</p>
                  </div>
                  <Badge variant={agent.status === "running" ? "warning" : "neutral"}>
                    {agent.status === "running" ? "Running" : "Idle"}
                  </Badge>
                </div>

                <div className="flex justify-between items-center pt-2 border-t border-white/5 text-[10px] text-muted-foreground font-mono">
                  <span>Last run: {agent.lastRun}</span>
                  <span>{agent.tokensUsed.toLocaleString()} tokens</span>
                  <Button
                    size="sm"
                    variant="neutral"
                    disabled={agent.status === "running"}
                    onClick={() => handleRunAgent(agent.id)}
                    className="h-6 px-2 py-0 text-[10px]"
                  >
                    {agent.status === "running" ? (
                      <>
                        <RefreshCw className="mr-1 size-3 animate-spin" /> Executing
                      </>
                    ) : (
                      <>
                        <Play className="mr-1 size-3" /> Run Agent
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Live Copilot Prompt Input */}
        <div className="rounded-base border border-border/80 bg-[#141418] p-3.5 space-y-3">
          <span className="flex items-center gap-1.5 text-foreground font-bold uppercase text-[10px] font-heading tracking-wider">
            <Sparkles className="size-3.5 text-purple-400" />
            Dispatch Agentic Instruction
          </span>
          <form onSubmit={handlePromptSubmit} className="flex gap-2">
            <Input
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              placeholder="e.g. Audit member permissions for Bangalore fork..."
              className="flex-1 text-xs"
            />
            <Button type="submit" disabled={isExecuting || !promptInput.trim()} size="sm">
              {isExecuting ? <RefreshCw className="size-3.5 animate-spin" /> : "Dispatch"}
            </Button>
          </form>
        </div>

        {/* Real-time Agent Log Stream */}
        <div className="rounded-base border border-border/80 bg-[#0d0d10] p-3 space-y-2 font-mono text-[10px]">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="flex items-center gap-1.5 text-amber-400 font-bold uppercase tracking-wider">
              <Terminal className="size-3.5" />
              Live Execution Telemetry
            </span>
            <span className="text-white/40">log-stream.0.2</span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto font-mono text-white/80">
            {logs.map((log, idx) => (
              <div key={idx} className="leading-relaxed break-all">
                {log}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
