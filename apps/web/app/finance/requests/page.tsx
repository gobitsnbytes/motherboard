"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";

const API = "";
const TABS = ["all", "pending", "approved", "rejected"] as const;
type Tab = typeof TABS[number];

interface MoneyReq {
  id: string; from_account_id: string | null; to_account_id: string;
  requester_id: string; amount_rupees: number; description: string;
  status: string; reviewed_by: string | null; reviewed_at: string | null;
  review_note: string | null; created_at: string;
  dual_approval_required?: boolean;
  approvals_count?: number;
  required_approvals?: number;
}

const STATUS_COLOR: Record<string, string> = { pending: "#fc920d", approved: "#22c55e", rejected: "#ef4444" };
const STATUS_BG: Record<string, string> = { pending: "rgba(252,146,13,0.08)", approved: "rgba(34,197,94,0.08)", rejected: "rgba(239,68,68,0.08)" };

export default function RequestsPage() {
  const [requests, setRequests] = useState<MoneyReq[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("all");
  const [reviewing, setReviewing] = useState<{ id: string; action: "approve" | "reject" } | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const getHeaders = (): Record<string, string> => ({ "Content-Type": "application/json" });

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "100" });
    if (tab !== "all") {
      params.set("status", tab);
    }
    fetch(`${API}/api/finance/requests?${params.toString()}`, { headers: getHeaders() })
      .then(r => r.json())
      .then(d => setRequests(Array.isArray(d) ? d : []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [tab]);

  const handleReview = async () => {
    if (!reviewing) return;
    setSubmitting(true);
    const endpoint = reviewing.action === "approve" ? "approve" : "reject";
    await fetch(`${API}/api/finance/requests/${reviewing.id}/${endpoint}`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ note: note || null }),
    });
    setReviewing(null);
    setNote("");
    setSubmitting(false);
    load();
  };

  const filtered = tab === "all" ? requests : requests.filter(r => r.status === tab);

  return (
    <div className="font-heading">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="m-0 font-heading text-[22px] font-extrabold text-white">Money Requests</h1>
          <p className="mt-1 font-base text-xs text-muted-foreground">Pool draws and inter-account transfers</p>
        </div>
        <Link href="/finance/requests/new"
          className="inline-block rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black no-underline shadow-shadow transition-transform hover:translate-x-[3px] hover:translate-y-[3px] hover:shadow-none">
          + New Request
        </Link>
      </div>

      {/* Tabs */}
      <div className="mb-5 flex gap-1 border-b-2 border-border pb-0">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`mb-[-2px] cursor-pointer border-b-2 border-transparent px-4 py-2 font-heading text-xs tracking-[0.05em] ${tab === t ? "border-orange font-bold text-orange" : "text-muted-foreground"}`}
            style={{ background: "transparent", textTransform: "capitalize", borderBottomColor: tab === t ? undefined : "transparent" }}>
            {t}
            {t !== "all" && <span className="ml-1.5 text-[10px]" style={{ color: STATUS_COLOR[t] ?? "#555" }}>
              {requests.filter(r => r.status === t).length}
            </span>}
          </button>
        ))}
      </div>

      {/* Review modal */}
      <AnimatePresence>
        {reviewing && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75">
            <motion.div initial={{ y: 20 }} animate={{ y: 0 }}
              className="w-[380px] rounded-base border-2 bg-main p-7"
              style={{
                borderColor: reviewing.action === "approve" ? "#22c55e" : "#ef4444",
                boxShadow: `6px 6px 0 0 ${reviewing.action === "approve" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
              }}>
              <h2 className="m-0 mb-4 font-heading text-[15px] font-extrabold capitalize text-white">
                {reviewing.action} Request
              </h2>
              <div>
                <label className="mb-1.5 block font-heading text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Note (optional)</label>
                <textarea value={note} onChange={e => setNote(e.target.value)} rows={3} placeholder="Add a note for the requester…"
                  className="box-border w-full resize-vertical rounded-base border-2 border-border bg-background px-3 py-2 font-base text-[13px] text-white outline-none focus:border-orange" />
              </div>
              <div className="mt-4 flex gap-2.5">
                <button onClick={handleReview} disabled={submitting}
                  className={`flex-1 rounded-base border-none py-2 font-heading text-xs font-bold ${reviewing.action === "approve" ? "bg-green-500 text-black" : "bg-red-500 text-black"} ${submitting ? "cursor-wait opacity-60" : "cursor-pointer"}`}>
                  {submitting ? "…" : reviewing.action === "approve" ? "Approve" : "Reject"}
                </button>
                <button onClick={() => { setReviewing(null); setNote(""); }}
                  className="flex-1 cursor-pointer rounded-base border-2 border-border bg-transparent py-2 font-heading text-xs text-muted-foreground">
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Request list */}
      {loading ? (
        <div className="font-base text-[13px] text-muted-foreground/50">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-border p-[60px_20px] text-center font-base text-muted-foreground/50">
          <div className="mb-2 text-sm">No {tab === "all" ? "" : tab} requests</div>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {filtered.map((r, i) => {
            const statusColor = STATUS_COLOR[r.status] ?? "#2a2a2a";
            const showDualProgress =
              r.dual_approval_required && r.status === "pending" && (r.required_approvals ?? 2) > 1;
            return (
              <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                <div
                  className="rounded-base border-2 p-4 px-[18px]"
                  style={{
                    background: STATUS_BG[r.status] ?? "var(--main)",
                    borderColor: r.status === "pending" ? undefined : `${statusColor}44`,
                    borderLeft: `4px solid ${statusColor}`,
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="mb-1.5 font-base text-sm font-semibold text-white/85">{r.description}</div>
                      <div className="flex flex-wrap items-center gap-4">
                        <span className="font-heading text-[10px] text-muted-foreground">
                          {r.from_account_id ? "account transfer" : "pool draw"} · {new Date(r.created_at).toLocaleDateString("en-IN")}
                        </span>
                        {showDualProgress && (
                          <span
                            className="rounded-base border-2 border-orange/40 bg-orange/10 px-1.5 py-0.5 font-heading text-[9px] font-bold uppercase tracking-[0.08em] text-orange"
                            title="Dual authorization (OKF Rule 35): two distinct approvers required before funds move"
                          >
                            {r.approvals_count ?? 0}/{r.required_approvals ?? 2} approvals
                          </span>
                        )}
                        {r.review_note && <span className="font-base text-[10px] italic text-muted-foreground">Note: {r.review_note}</span>}
                      </div>
                    </div>
                    <div className="ml-4 flex shrink-0 items-center gap-3">
                      <div className="text-right">
                        <div className="font-heading text-lg font-extrabold text-white">₹{r.amount_rupees.toLocaleString("en-IN")}</div>
                        <div className="font-heading text-[9px] font-bold uppercase tracking-[0.1em]" style={{ color: statusColor }}>{r.status}</div>
                      </div>
                      {r.status === "pending" && (
                        <div className="flex flex-col gap-1.5">
                          <button onClick={() => setReviewing({ id: r.id, action: "approve" })}
                            className="cursor-pointer rounded-base border-none bg-green-500 px-3 py-1 font-heading text-[10px] font-bold text-black">
                            Approve
                          </button>
                          <button onClick={() => setReviewing({ id: r.id, action: "reject" })}
                            className="cursor-pointer rounded-base border border-red-500 bg-transparent px-3 py-1 font-heading text-[10px] font-semibold text-red-500">
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
