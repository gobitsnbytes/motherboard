"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Inbox,
  Loader2,
  MailQuestion,
  RefreshCw,
  Send,
  ShieldAlert,
  Stamp,
  Timer,
} from "lucide-react";
import {
  askLegalAgent,
  fetchAgentStats,
  fetchInboundContracts,
  type AgentStats,
  type AskResponse,
  type PipelineContractItem,
} from "lib/legal-agent";

function riskBadgeClass(risk: string) {
  switch (risk) {
    case "high":
      return "bg-red-500/15 text-red-400 border-red-500/40";
    case "medium":
      return "bg-orange/10 text-orange border-orange/40";
    case "low":
      return "bg-green-500/10 text-green-400 border-green-500/40";
    default:
      return "bg-blank text-muted-foreground border-border";
  }
}

function StatTile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-base border-2 border-border bg-blank px-2.5 py-2">
      <div className="font-heading text-lg font-black text-main-foreground">{value}</div>
      <div className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="space-y-2 rounded-base border-2 border-border bg-blank p-3">
      <div className="h-3 w-3/4 animate-pulse rounded-base bg-white/10" />
      <div className="h-2.5 w-1/2 animate-pulse rounded-base bg-white/5" />
    </div>
  );
}

export default function LegalAgentPanel() {
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [inbound, setInbound] = useState<PipelineContractItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askResult, setAskResult] = useState<AskResponse | null>(null);
  const [askError, setAskError] = useState<string | null>(null);
  const answerRef = useRef<HTMLDivElement | null>(null);

  const loadAll = useCallback(async () => {
    setError(null);
    setLoading(true);
    const results = await Promise.allSettled([fetchAgentStats(), fetchInboundContracts()]);
    const [statsRes, inboundRes] = results;
    if (statsRes.status === "fulfilled") setStats(statsRes.value);
    if (inboundRes.status === "fulfilled") setInbound(inboundRes.value);
    if (statsRes.status === "rejected" && inboundRes.status === "rejected") {
      setError("Legal Agent API unreachable. Try again shortly.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (answerRef.current) {
      answerRef.current.scrollTop = answerRef.current.scrollHeight;
    }
  }, [askResult]);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setAskError(null);
    try {
      const res = await askLegalAgent(q);
      setAskResult(res);
      setQuestion("");
    } catch {
      setAskError("Could not reach the legal knowledge base.");
    } finally {
      setAsking(false);
    }
  };

  const lastPollLabel = (() => {
    if (!stats?.last_poll_at) return "Never";
    const mins = Math.max(
      0,
      Math.round((Date.now() - new Date(stats.last_poll_at).getTime()) / 60000),
    );
    return mins === 0 ? "Just now" : `${mins}m ago`;
  })();

  return (
    <section aria-label="Legal Agent Inbox" className="space-y-4">
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between rounded-base border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-xs font-bold text-red-300"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={loadAll}
            className="inline-flex items-center gap-1.5 rounded-base border border-border px-2 py-1 hover:bg-white/5"
          >
            <RefreshCw className="size-3" /> Retry
          </button>
        </div>
      )}

      {/* Three-column responsive layout */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* (a) Inbox — recent inbound threads */}
        <div className="rounded-base border-2 border-border bg-blank p-4 shadow-shadow">
          <div className="mb-3 flex items-center justify-between">
            <span className="flex items-center gap-1.5 font-heading text-[11px] font-bold uppercase tracking-wider text-burgundy">
              <Inbox className="size-3.5" /> Legal Inbox
            </span>
            <button
              type="button"
              onClick={loadAll}
              title="Refresh inbox"
              className="rounded-base border border-border p-1 text-muted-foreground hover:bg-white/5"
            >
              <RefreshCw className={`size-3 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {loading ? (
            <div className="space-y-2">
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : inbound.length === 0 ? (
            <div className="space-y-2 py-8 text-center">
              <MailQuestion className="mx-auto size-7 text-muted-foreground" />
              <p className="text-xs font-bold text-main-foreground">No inbound contracts yet</p>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Email a contract to{" "}
                <span className="font-mono text-orange">legal@gobitsnbytes.org</span> and it will
                appear here fully analysed.
              </p>
            </div>
          ) : (
            <ul className="max-h-80 space-y-2 overflow-y-auto pr-0.5">
              {inbound.map((c) => (
                <li
                  key={c.id}
                  className="rounded-base border-2 border-border bg-blank p-3 transition-colors hover:border-burgundy/50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-heading text-xs font-bold text-main-foreground">{c.title}</p>
                    <span
                      className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-black uppercase ${riskBadgeClass(c.highest_risk)}`}
                      title={`${c.high_risks} high / ${c.medium_risks} medium / ${c.low_risks} low`}
                    >
                      {c.highest_risk === "none" ? "clean" : `${c.highest_risk} risk`}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-[10px] text-muted-foreground" title={c.counterparty}>
                    from: {c.counterparty}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    received{" "}
                    {new Date(c.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    {" · "}
                    {c.days_in_stage}d in review
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* (b) Pipeline mini-board + nudge chips */}
        <div className="rounded-base border-2 border-border bg-blank p-4 shadow-shadow">
          <span className="mb-3 flex items-center gap-1.5 font-heading text-[11px] font-bold uppercase tracking-wider text-orange">
            <Stamp className="size-3.5" /> Contract Pipeline
          </span>

          <div className="grid grid-cols-3 gap-2">
            <StatTile label="In Review" value={stats?.contracts_in_review ?? "–"} />
            <StatTile label="Out for Sig" value={stats?.out_for_signature ?? "–"} />
            <StatTile label="Dotted" value={stats?.dotted_count ?? "–"} />
          </div>

          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between rounded-base border-2 border-border bg-blank px-3 py-2">
              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                <ShieldAlert className="size-3.5 text-burgundy" /> Nudges due
              </span>
              <span
                className={`rounded border px-2 py-0.5 font-heading text-xs font-black ${
                  (stats?.pending_nudges ?? 0) > 0
                    ? "border-orange/40 bg-orange/10 text-orange"
                    : "border-border text-muted-foreground"
                }`}
              >
                {stats ? stats.pending_nudges : "–"}
              </span>
            </div>

            <div className="flex flex-wrap gap-1.5" aria-label="Nudge cadence">
              {["3d nudge", "7d nudge", "14d final"].map((chip) => (
                <span
                  key={chip}
                  className="inline-flex items-center gap-1 rounded-base border border-border bg-blank px-2 py-0.5 text-[9px] font-bold uppercase text-muted-foreground"
                >
                  <Timer className="size-2.5" /> {chip}
                </span>
              ))}
            </div>

            <p className="text-[10px] text-muted-foreground">
              Last inbox poll: <span className="font-bold text-main-foreground">{lastPollLabel}</span>
              {" · "}
              {stats ? stats.inbox_processed_24h : "–"} processed (24h)
            </p>
          </div>
        </div>

        {/* (c) Ask-your-contracts */}
        <div className="flex flex-col rounded-base border-2 border-border bg-blank p-4 shadow-shadow">
          <span className="mb-3 flex items-center gap-1.5 font-heading text-[11px] font-bold uppercase tracking-wider text-burgundy">
            <MailQuestion className="size-3.5" /> Ask Your Contracts
          </span>

          <form onSubmit={handleAsk} className="flex flex-col gap-2">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder="e.g. What is the liability cap in the Master Services Agreement?"
              className="w-full resize-none rounded-base border-2 border-border bg-blank p-2.5 text-xs text-main-foreground placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-burgundy"
            />
            <button
              type="submit"
              disabled={asking || !question.trim()}
              className="inline-flex items-center justify-center gap-2 rounded-base border-2 border-border bg-burgundy px-3 py-2 font-heading text-[11px] font-bold uppercase tracking-wider text-main-foreground shadow-shadow transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:cursor-not-allowed disabled:opacity-40"
            >
              {asking ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
              {asking ? "Thinking…" : "Ask"}
            </button>
          </form>

          {askError && (
            <p role="alert" className="mt-2 flex items-center gap-1 text-[11px] font-bold text-red-400">
              <AlertTriangle className="size-3" /> {askError}
            </p>
          )}

          <div ref={answerRef} className="mt-3 max-h-56 flex-1 overflow-y-auto">
            {!askResult && !asking && (
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Answers are grounded in the OKF playbook and your executed contracts only.
              </p>
            )}
            {asking && (
              <div className="space-y-2 pt-1">
                <div className="h-2.5 w-full animate-pulse rounded-base bg-white/10" />
                <div className="h-2.5 w-5/6 animate-pulse rounded-base bg-white/10" />
                <div className="h-2.5 w-2/3 animate-pulse rounded-base bg-white/5" />
              </div>
            )}
            {askResult && (
              <div className="space-y-2">
                <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-main-foreground">
                  {askResult.answer}
                </p>
                {askResult.sources.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {askResult.sources.map((s, i) => (
                      <span
                        key={`${s.label}-${s.title}-${i}`}
                        title={s.title}
                        className={`max-w-full truncate rounded border px-1.5 py-0.5 text-[9px] font-bold ${
                          s.label === "Executed Contract"
                            ? "border-burgundy/50 bg-burgundy/10 text-burgundy"
                            : "border-orange/50 bg-orange/10 text-orange"
                        }`}
                      >
                        {s.label}: {s.title}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
