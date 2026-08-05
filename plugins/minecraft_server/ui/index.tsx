"use client";

import React, { useEffect, useState } from "react";
import {
  Gamepad2,
  Server,
  Users,
  Activity,
  Terminal,
  RefreshCw,
  Play,
  Square,
  RotateCcw,
  Shield,
  Zap,
  HardDrive,
  Cpu,
  Clock,
  AlertCircle,
  CheckCircle2,
  Send,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
  Input,
  Skeleton,
} from "@bnb/ui";

interface ServerStatus {
  online: bool;
  host: string;
  port: number;
  ssh_host: string;
  latency_ms?: number;
  motd?: string;
  version?: string;
  players_online: number;
  max_players: number;
  service_status: string;
  last_checked: string;
}

interface Player {
  name: string;
  uuid?: string;
  avatar_url: string;
}

interface Metrics {
  tps: number;
  cpu_usage_pct?: number;
  ram_used_mb?: number;
  ram_max_mb?: number;
  disk_used_gb?: number;
  uptime?: string;
}

export default function MinecraftServerUI() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [command, setCommand] = useState("");
  const [commandOutput, setCommandOutput] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const [statusRes, playersRes, metricsRes, logsRes] = await Promise.all([
        fetch("/api/plugins/minecraft_server/status").then((r) => r.ok ? r.json() : null),
        fetch("/api/plugins/minecraft_server/players").then((r) => r.ok ? r.json() : null),
        fetch("/api/plugins/minecraft_server/metrics").then((r) => r.ok ? r.json() : null),
        fetch("/api/plugins/minecraft_server/logs").then((r) => r.ok ? r.json() : null),
      ]);

      if (statusRes) setStatus(statusRes);
      if (playersRes) setPlayers(playersRes.players || []);
      if (metricsRes) setMetrics(metricsRes);
      if (logsRes) setLogs(logsRes.lines || []);
    } catch (err) {
      console.error("Failed to load Minecraft server data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleExecuteCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;

    setExecuting(true);
    try {
      const res = await fetch("/api/plugins/minecraft_server/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command }),
      });
      const data = await res.json();
      if (res.ok) {
        setCommandOutput(`> ${command}\n${data.output}`);
        setCommand("");
      } else {
        setCommandOutput(`Error: ${data.detail || "Command failed"}`);
      }
    } catch (err) {
      setCommandOutput(`Execution failed: ${err}`);
    } finally {
      setExecuting(false);
    }
  };

  const handleAction = async (action: string) => {
    setActionLoading(action);
    try {
      const res = await fetch("/api/plugins/minecraft_server/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      alert(data.message || `Action ${action} disptached.`);
      fetchAllData();
    } catch (err) {
      alert(`Action failed: ${err}`);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-base border-2 border-border bg-[#97192C] p-6 text-white shadow-shadow">
        <div>
          <div className="flex items-center gap-2">
            <Gamepad2 className="size-6 text-[#FC920D]" />
            <h1 className="font-heading font-extrabold text-2xl tracking-wide">
              Minecraft Server Management
            </h1>
          </div>
          <p className="mt-1 text-xs text-white/80 font-base">
            Live infrastructure control for <code className="bg-black/40 px-1.5 py-0.5 rounded font-mono text-[#FC920D]">mc.gobitsnbytes.org</code> (SSH: <code className="bg-black/40 px-1.5 py-0.5 rounded font-mono">bnb-mc-server</code>)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={fetchAllData}
            variant="neutral"
            className="border-2 border-border bg-[#111] text-white hover:bg-[#222]"
          >
            <RefreshCw className={`size-4 mr-1.5 ${loading ? "animate-spin text-[#FC920D]" : ""}`} />
            Refresh Status
          </Button>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Server Status
            </CardTitle>
            <Server className="size-4 text-[#FC920D]" />
          </CardHeader>
          <CardContent>
            {loading && !status ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="flex items-center gap-2">
                <Badge variant={status?.online ? "success" : "danger"} className="text-xs">
                  {status?.online ? "ONLINE" : "OFFLINE"}
                </Badge>
                <span className="text-xs font-mono text-muted-foreground">
                  {status?.latency_ms ? `${status.latency_ms}ms` : ""}
                </span>
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-2 font-mono">
              Port: 25565 &bull; SSH: bnb-mc-server
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Online Players
            </CardTitle>
            <Users className="size-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {loading && !status ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {status?.players_online ?? 0} / {status?.max_players ?? 20}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Active builder sessions</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Performance TPS
            </CardTitle>
            <Activity className="size-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            {loading && !metrics ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-green-400">
                {metrics?.tps ?? 20.0} <span className="text-xs text-muted-foreground font-normal">/ 20.0</span>
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Target: 20 Ticks Per Second</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Server Version
            </CardTitle>
            <Shield className="size-4 text-[#97192C]" />
          </CardHeader>
          <CardContent>
            <div className="font-heading font-bold text-sm text-foreground truncate">
              {status?.version || "Minecraft 1.20.4+"}
            </div>
            <p className="text-[11px] text-muted-foreground mt-1 truncate">
              {status?.motd || "bits&bytes™ Official Network"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Control Actions Bar */}
      <Card className="border-2 border-border shadow-shadow">
        <CardHeader className="pb-3 border-b-2 border-border">
          <CardTitle className="font-heading font-bold text-base flex items-center gap-2">
            <Zap className="size-5 text-[#FC920D]" />
            Server Lifecycle Controls
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4 flex flex-wrap gap-3">
          <Button
            onClick={() => handleAction("restart")}
            disabled={actionLoading === "restart"}
            variant="neutral"
            className="border-2 border-border bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30"
          >
            <RotateCcw className="size-4 mr-2" />
            Restart Server
          </Button>

          <Button
            onClick={() => handleAction("stop")}
            disabled={actionLoading === "stop"}
            variant="neutral"
            className="border-2 border-border bg-red-500/20 text-red-300 hover:bg-red-500/30"
          >
            <Square className="size-4 mr-2" />
            Stop Server
          </Button>

          <Button
            onClick={() => handleAction("start")}
            disabled={actionLoading === "start"}
            variant="neutral"
            className="border-2 border-border bg-green-500/20 text-green-300 hover:bg-green-500/30"
          >
            <Play className="size-4 mr-2" />
            Start Server
          </Button>

          <Button
            onClick={() => handleAction("backup")}
            disabled={actionLoading === "backup"}
            variant="neutral"
            className="border-2 border-border bg-blue-500/20 text-blue-300 hover:bg-blue-500/30"
          >
            <HardDrive className="size-4 mr-2" />
            Create Backup
          </Button>
        </CardContent>
      </Card>

      {/* Main 2-Column Section */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left: Console / RCON Command Prompt */}
        <Card className="border-2 border-border shadow-shadow flex flex-col">
          <CardHeader className="border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <Terminal className="size-5 text-[#FC920D]" />
              <CardTitle className="font-heading font-bold text-base">RCON Command Console</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-4 flex-1 flex flex-col space-y-4">
            <div className="bg-[#111] border-2 border-border rounded-base p-3 font-mono text-xs text-green-400 min-h-[160px] max-h-[220px] overflow-y-auto whitespace-pre-wrap">
              {commandOutput || "# Ready for RCON commands (e.g. /op, /whitelist, /say, /save-all)"}
            </div>

            <form onSubmit={handleExecuteCommand} className="flex gap-2">
              <Input
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="Enter RCON command (e.g. list, say Hello, op yash)..."
                className="font-mono text-xs bg-[#111] text-white flex-1"
              />
              <Button type="submit" disabled={executing} className="bg-[#97192C] text-white">
                <Send className="size-4" />
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Right: Connected Players */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="border-b-2 border-border pb-4 flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="size-5 text-green-500" />
              <CardTitle className="font-heading font-bold text-base">Connected Players ({players.length})</CardTitle>
            </div>
            <Badge variant="neutral" className="text-[10px]">Real-time RCON Query</Badge>
          </CardHeader>
          <CardContent className="pt-4">
            {players.length === 0 ? (
              <div className="text-center py-8 text-xs text-muted-foreground">
                No players currently online on mc.gobitsnbytes.org
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {players.map((p) => (
                  <div key={p.name} className="flex items-center gap-2.5 bg-[#111] border-2 border-border p-2 rounded-base">
                    <img src={p.avatar_url} alt={p.name} className="size-8 rounded border border-border bg-black/50" />
                    <span className="font-mono font-bold text-xs text-white truncate">{p.name}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Live Server Logs */}
      <Card className="border-2 border-border shadow-shadow">
        <CardHeader className="border-b-2 border-border pb-4 flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="size-5 text-muted-foreground" />
            <CardTitle className="font-heading font-bold text-base">Server Output Stream (journalctl / latest.log)</CardTitle>
          </div>
          <Badge variant="neutral" className="font-mono text-[10px]">Tail 50 lines</Badge>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="bg-black/90 border-2 border-border rounded-base p-4 font-mono text-[11px] text-green-400/90 h-64 overflow-y-auto space-y-1">
            {logs.length === 0 ? (
              <div className="text-muted-foreground">Waiting for log stream...</div>
            ) : (
              logs.map((line, idx) => (
                <div key={idx} className="leading-tight hover:bg-white/5 px-1 rounded">{line}</div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
