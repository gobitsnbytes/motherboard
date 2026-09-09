"use client";

import React, { useEffect, useState } from "react";
import {
  Mail,
  Server,
  ShieldCheck,
  Globe,
  RefreshCw,
  Zap,
  RotateCcw,
  ListOrdered,
  Terminal,
  CheckCircle2,
  AlertTriangle,
  Lock,
  ExternalLink,
  Send,
  SlidersHorizontal,
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

interface PortStatus {
  service: string;
  port: number;
  open: boolean;
  latency_ms?: number;
}

interface ServerStatus {
  mail_domain: string;
  admin_domain: string;
  ssh_host: string;
  all_healthy: boolean;
  ports: PortStatus[];
  webmail_status: string;
  admin_console_status: string;
  last_checked: string;
}

interface DnsRecord {
  record_type: string;
  domain: string;
  expected: string;
  actual: string;
  valid: boolean;
  details: string;
}

interface DnsSecurity {
  base_domain: string;
  mail_domain: string;
  admin_domain: string;
  records: DnsRecord[];
  ssl_cert_days_remaining?: number;
  all_valid: boolean;
}

interface QueueStatus {
  queue_length: number;
  active_count: number;
  deferred_count: number;
}

export default function EmailServerUI() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [dns, setDns] = useState<DnsSecurity | null>(null);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const [statusRes, dnsRes, queueRes, logsRes] = await Promise.all([
        fetch("/api/plugins/email_server/status").then((r) => (r.ok ? r.json() : null)),
        fetch("/api/plugins/email_server/dns").then((r) => (r.ok ? r.json() : null)),
        fetch("/api/plugins/email_server/queue").then((r) => (r.ok ? r.json() : null)),
        fetch("/api/plugins/email_server/logs").then((r) => (r.ok ? r.json() : null)),
      ]);

      if (statusRes) setStatus(statusRes);
      if (dnsRes) setDns(dnsRes);
      if (queueRes) setQueue(queueRes);
      if (logsRes) setLogs(logsRes.lines || []);
    } catch (err) {
      console.error("Failed to load Email server data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (action: string) => {
    setActionLoading(action);
    try {
      const res = await fetch("/api/plugins/email_server/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      alert(data.message || `Action ${action} completed.`);
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
            <Mail className="size-6 text-[#FC920D]" />
            <h1 className="font-heading font-extrabold text-2xl tracking-wide">
              Email Infrastructure Management
            </h1>
          </div>
          <p className="mt-1 text-xs text-white/80 font-base">
            Domains: <code className="bg-black/40 px-1.5 py-0.5 rounded font-mono text-[#FC920D]">mail.gobitsnbytes.org</code> &bull; <code className="bg-black/40 px-1.5 py-0.5 rounded font-mono text-[#FC920D]">admin.gobitsnbytes.org</code> (SSH: <code className="bg-black/40 px-1.5 py-0.5 rounded font-mono">bnb-backend</code>)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={fetchAllData}
            variant="neutral"
            className="border-2 border-border bg-[#111] text-white hover:bg-[#222]"
          >
            <RefreshCw className={`size-4 mr-1.5 ${loading ? "animate-spin text-[#FC920D]" : ""}`} />
            Refresh Infrastructure
          </Button>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Mail Server Health
            </CardTitle>
            <Server className="size-4 text-[#FC920D]" />
          </CardHeader>
          <CardContent>
            {loading && !status ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="flex items-center gap-2">
                <Badge variant={status?.all_healthy ? "success" : "warning"} className="text-xs">
                  {status?.all_healthy ? "HEALTHY" : "DEGRADED"}
                </Badge>
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-2 font-mono">
              Host: bnb-backend
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Outgoing Mail Queue
            </CardTitle>
            <ListOrdered className="size-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            {loading && !queue ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {queue?.queue_length ?? 0} <span className="text-xs text-muted-foreground font-normal">messages</span>
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">
              {queue?.deferred_count ?? 0} deferred &bull; {queue?.active_count ?? 0} active
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              DNS Security Rules
            </CardTitle>
            <ShieldCheck className="size-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {loading && !dns ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="flex items-center gap-2">
                <Badge variant={dns?.all_valid ? "success" : "danger"} className="text-xs">
                  MX &bull; SPF &bull; DKIM &bull; DMARC
                </Badge>
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-2">
              {dns ? (dns.all_valid ? "100% Policy Alignment" : "Policy Drift Detected") : "Awaiting live DNS check"}
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              SSL / TLS Certs
            </CardTitle>
            <Lock className="size-4 text-green-400" />
          </CardHeader>
          <CardContent>
            <div className="font-heading font-bold text-sm text-foreground">
              {dns && dns.ssl_cert_days_remaining != null
                ? `${dns.ssl_cert_days_remaining} Days Remaining`
                : "Cert Status Unavailable"}
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">
              {dns?.ssl_cert_days_remaining != null
                ? "Auto-renew via Let's Encrypt"
                : "Live certificate could not be retrieved"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Domain Port Matrix & Controls */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left: Port Service Matrix */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="border-b-2 border-border pb-4 flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="size-5 text-[#FC920D]" />
              <CardTitle className="font-heading font-bold text-base">Service Port Matrix (mail.gobitsnbytes.org)</CardTitle>
            </div>
            <Badge variant="neutral" className="font-mono text-[10px]">TCP Check</Badge>
          </CardHeader>
          <CardContent className="pt-4 space-y-2.5">
            {loading && !status ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              status?.ports.map((p) => (
                <div key={p.port} className="flex items-center justify-between bg-[#111] border border-border/60 p-2.5 rounded-base text-xs">
                  <div className="flex items-center gap-2">
                    <div className={`size-2.5 rounded-full ${p.open ? "bg-green-500" : "bg-red-500"}`} />
                    <span className="font-heading font-bold text-white">{p.service}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">Port {p.port}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-muted-foreground">{p.latency_ms ? `${p.latency_ms}ms` : ""}</span>
                    <Badge variant={p.open ? "success" : "danger"} className="text-[9px]">
                      {p.open ? "OPEN" : "CLOSED"}
                    </Badge>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Right: Quick Operational Controls */}
        <Card className="border-2 border-border shadow-shadow flex flex-col">
          <CardHeader className="border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <Zap className="size-5 text-[#97192C]" />
              <CardTitle className="font-heading font-bold text-base">Mail Infrastructure Actions</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-3 flex-1">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Button
                onClick={() => handleAction("flush_queue")}
                disabled={actionLoading === "flush_queue"}
                variant="neutral"
                className="border-2 border-border bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 text-xs justify-start"
              >
                <Send className="size-4 mr-2" />
                Flush Mail Queue
              </Button>

              <Button
                onClick={() => handleAction("restart_postfix")}
                disabled={actionLoading === "restart_postfix"}
                variant="neutral"
                className="border-2 border-border bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30 text-xs justify-start"
              >
                <RotateCcw className="size-4 mr-2" />
                Restart Postfix
              </Button>

              <Button
                onClick={() => handleAction("restart_dovecot")}
                disabled={actionLoading === "restart_dovecot"}
                variant="neutral"
                className="border-2 border-border bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 text-xs justify-start"
              >
                <RotateCcw className="size-4 mr-2" />
                Restart Dovecot
              </Button>

              <Button
                onClick={() => handleAction("reload_nginx")}
                disabled={actionLoading === "reload_nginx"}
                variant="neutral"
                className="border-2 border-border bg-green-500/20 text-green-300 hover:bg-green-500/30 text-xs justify-start"
              >
                <RefreshCw className="size-4 mr-2" />
                Reload Nginx Domains
              </Button>
            </div>

            {/* Target Domains summary box */}
            <div className="mt-4 p-3 bg-[#111] border-2 border-border rounded-base text-xs space-y-2">
              <div className="font-heading font-bold text-white flex items-center justify-between">
                <span>Webmail Portal</span>
                <a href="https://mail.gobitsnbytes.org" target="_blank" rel="noreferrer" className="text-[#FC920D] hover:underline flex items-center gap-1 text-[11px]">
                  mail.gobitsnbytes.org <ExternalLink className="size-3" />
                </a>
              </div>
              <div className="font-heading font-bold text-white flex items-center justify-between border-t border-border/40 pt-2">
                <span>Admin Console</span>
                <a href="https://admin.gobitsnbytes.org" target="_blank" rel="noreferrer" className="text-[#FC920D] hover:underline flex items-center gap-1 text-[11px]">
                  admin.gobitsnbytes.org <ExternalLink className="size-3" />
                </a>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* DNS Records Checklist */}
      <Card className="border-2 border-border shadow-shadow">
        <CardHeader className="border-b-2 border-border pb-4">
          <div className="flex items-center gap-2">
            <Globe className="size-5 text-[#FC920D]" />
            <CardTitle className="font-heading font-bold text-base">DNS Security & Authentication Verification</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="space-y-2.5">
            {dns?.records.map((r, idx) => (
              <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between bg-[#111] border-2 border-border p-3 rounded-base gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge variant="neutral" className="font-mono text-[10px] bg-[#97192C] text-white border-0">
                      {r.record_type}
                    </Badge>
                    <span className="font-mono font-bold text-xs text-white">{r.domain}</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">{r.details}</p>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  <span
                    className={`font-mono text-[10px] px-2 py-1 rounded border ${
                      r.valid
                        ? "text-green-400 bg-green-500/10 border-green-500/20"
                        : "text-red-400 bg-red-500/10 border-red-500/20"
                    }`}
                  >
                    {r.actual}
                  </span>
                  {r.valid ? (
                    <CheckCircle2 className="size-4 text-green-500" />
                  ) : (
                    <AlertTriangle className="size-4 text-red-500" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Live Mail Output Stream */}
      <Card className="border-2 border-border shadow-shadow">
        <CardHeader className="border-b-2 border-border pb-4 flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="size-5 text-muted-foreground" />
            <CardTitle className="font-heading font-bold text-base">Live Mail Logs (journalctl -u postfix -u dovecot)</CardTitle>
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
