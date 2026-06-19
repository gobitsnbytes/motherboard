"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TABS = ["all", "pending", "approved", "rejected"] as const;
type Tab = typeof TABS[number];

interface MoneyReq {
  id: string; from_account_id: string | null; to_account_id: string;
  requester_id: string; amount_rupees: number; description: string;
  status: string; reviewed_by: string | null; reviewed_at: string | null;
  review_note: string | null; created_at: string;
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

  const getHeaders = (): Record<string, string> => {
    const uid = typeof window !== "undefined" ? localStorage.getItem("x-user-id") : null;
    return uid ? { "X-User-Id": uid, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  };

  const load = () => {
    setLoading(true);
    const q = tab !== "all" ? `?status=${tab}` : "";
    fetch(`${API}/api/finance/requests${q}&limit=100`, { headers: getHeaders() })
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
    <div style={{ fontFamily: "Inter, sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#fff", margin: 0 }}>Money Requests</h1>
          <p style={{ fontSize: "12px", color: "#555", marginTop: "4px" }}>Pool draws and inter-account transfers</p>
        </div>
        <Link href="/finance/requests/new"
          style={{ padding: "9px 16px", background: "#fc920d", border: "2px solid #fc920d", borderRadius: "3px", color: "#000", fontWeight: 700, fontSize: "12px", textDecoration: "none", display: "inline-block", boxShadow: "3px 3px 0 0 rgba(252,146,13,0.4)" }}>
          + New Request
        </Link>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "20px", borderBottom: "2px solid #1e1e1e", paddingBottom: "0" }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding: "8px 16px", background: "transparent", border: "none", borderBottom: tab === t ? "2px solid #fc920d" : "2px solid transparent",
              color: tab === t ? "#fc920d" : "#555", fontFamily: "Inter, sans-serif", fontWeight: tab === t ? 700 : 400,
              fontSize: "12px", cursor: "pointer", textTransform: "capitalize", letterSpacing: "0.05em", marginBottom: "-2px",
            }}>
            {t}
            {t !== "all" && <span style={{ marginLeft: "6px", fontSize: "10px", color: STATUS_COLOR[t] ?? "#555" }}>
              {requests.filter(r => r.status === t).length}
            </span>}
          </button>
        ))}
      </div>

      {/* Review modal */}
      <AnimatePresence>
        {reviewing && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <motion.div initial={{ y: 20 }} animate={{ y: 0 }}
              style={{ background: "#111", border: `2px solid ${reviewing.action === "approve" ? "#22c55e" : "#ef4444"}`, borderRadius: "4px", padding: "28px", width: "380px", boxShadow: `6px 6px 0 0 ${reviewing.action === "approve" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}` }}>
              <h2 style={{ fontSize: "15px", fontWeight: 800, color: "#fff", margin: "0 0 16px", textTransform: "capitalize" }}>
                {reviewing.action} Request
              </h2>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Note (optional)</label>
                <textarea value={note} onChange={e => setNote(e.target.value)} rows={3} placeholder="Add a note for the requester…"
                  style={{ width: "100%", background: "#0d0d0d", border: "2px solid #2a2a2a", borderRadius: "3px", padding: "9px 12px", color: "#fff", fontFamily: "Inter, sans-serif", fontSize: "13px", resize: "vertical", outline: "none", boxSizing: "border-box" }} />
              </div>
              <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
                <button onClick={handleReview} disabled={submitting}
                  style={{ flex: 1, padding: "9px", background: reviewing.action === "approve" ? "#22c55e" : "#ef4444", border: "none", borderRadius: "3px", color: "#000", fontWeight: 700, fontSize: "12px", cursor: "pointer", opacity: submitting ? 0.6 : 1 }}>
                  {submitting ? "…" : reviewing.action === "approve" ? "Approve" : "Reject"}
                </button>
                <button onClick={() => { setReviewing(null); setNote(""); }}
                  style={{ flex: 1, padding: "9px", background: "transparent", border: "2px solid #2a2a2a", borderRadius: "3px", color: "#888", fontSize: "12px", cursor: "pointer" }}>
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Request list */}
      {loading ? (
        <div style={{ color: "#333", fontSize: "13px" }}>Loading…</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: "60px 20px", border: "2px dashed #1e1e1e", borderRadius: "4px", color: "#333" }}>
          <div style={{ fontSize: "14px", marginBottom: "8px" }}>No {tab === "all" ? "" : tab} requests</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {filtered.map((r, i) => (
            <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
              <div style={{
                background: STATUS_BG[r.status] ?? "#111",
                border: `2px solid ${r.status === "pending" ? "#2a2a2a" : STATUS_COLOR[r.status] + "44"}`,
                borderLeft: `4px solid ${STATUS_COLOR[r.status] ?? "#2a2a2a"}`,
                borderRadius: "4px",
                padding: "16px 18px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "14px", fontWeight: 600, color: "#ddd", marginBottom: "6px" }}>{r.description}</div>
                    <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                      <span style={{ fontSize: "10px", color: "#555" }}>
                        {r.from_account_id ? "account transfer" : "pool draw"} · {new Date(r.created_at).toLocaleDateString("en-IN")}
                      </span>
                      {r.review_note && <span style={{ fontSize: "10px", color: "#666", fontStyle: "italic" }}>Note: {r.review_note}</span>}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", marginLeft: "16px", flexShrink: 0 }}>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "18px", fontWeight: 800, color: "#fff" }}>₹{r.amount_rupees.toLocaleString("en-IN")}</div>
                      <div style={{ fontSize: "9px", color: STATUS_COLOR[r.status], textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.1em" }}>{r.status}</div>
                    </div>
                    {r.status === "pending" && (
                      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        <button onClick={() => setReviewing({ id: r.id, action: "approve" })}
                          style={{ padding: "5px 12px", background: "#22c55e", border: "none", borderRadius: "3px", color: "#000", fontSize: "10px", fontWeight: 700, cursor: "pointer" }}>
                          Approve
                        </button>
                        <button onClick={() => setReviewing({ id: r.id, action: "reject" })}
                          style={{ padding: "5px 12px", background: "transparent", border: "1px solid #ef4444", borderRadius: "3px", color: "#ef4444", fontSize: "10px", fontWeight: 600, cursor: "pointer" }}>
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
