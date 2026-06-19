"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Account { id: string; name: string; balance_rupees: number; is_active: boolean; account_number: string; }
interface MoneyReq { id: string; amount_rupees: number; status: string; description: string; created_at: string; }
interface Transaction { id: string; source_account_id: string | null; destination_account_id: string | null; amount_rupees: number; amount_paise: number; reference_type: string; reference_id: string | null; description: string; created_at: string; }

function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{
        background: "#111",
        border: "2px solid #1e1e1e",
        borderRadius: "4px",
        padding: "20px 22px",
        boxShadow: `4px 4px 0 0 ${accent ?? "#1e1e1e"}`,
        flex: 1,
        minWidth: "160px",
      }}
    >
      <div style={{ fontFamily: "Inter, sans-serif", fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.15em", color: "#555", marginBottom: "10px" }}>{label}</div>
      <div style={{ fontFamily: "Inter, sans-serif", fontSize: "28px", fontWeight: 800, color: "#fff", lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontFamily: "Inter, sans-serif", fontSize: "11px", color: "#444", marginTop: "6px" }}>{sub}</div>}
    </motion.div>
  );
}

export default function FinanceDashboard() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [requests, setRequests] = useState<MoneyReq[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const userId = localStorage.getItem("x-user-id");
    const headers: Record<string, string> = userId ? { "X-User-Id": userId } : {};

    Promise.all([
      fetch(`${API}/api/finance/accounts`, { headers }).then((r) => r.json()),
      fetch(`${API}/api/finance/requests?limit=10`, { headers }).then((r) => r.json()),
      fetch(`${API}/api/finance/transactions?limit=6`, { headers }).then((r) => r.json()),
    ])
      .then(([accs, reqs, txs]) => {
        setAccounts(Array.isArray(accs) ? accs : []);
        setRequests(Array.isArray(reqs) ? reqs : []);
        setTransactions(Array.isArray(txs) ? txs : []);
      })
      .catch(() => setError("Could not load finance data. Check API connection."))
      .finally(() => setLoading(false));
  }, []);

  const totalBalance = accounts.reduce((s, a) => s + a.balance_rupees, 0);
  const pending = requests.filter((r) => r.status === "pending").length;

  return (
    <div style={{ fontFamily: "Inter, sans-serif" }}>
      {/* Page title */}
      <div style={{ marginBottom: "28px" }}>
        <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#fff", margin: 0, letterSpacing: "-0.01em" }}>Dashboard</h1>
        <p style={{ fontSize: "12px", color: "#555", marginTop: "4px" }}>
          Virtual ledger overview · all balances are internal paper values
        </p>
      </div>

      {error && (
        <div style={{ background: "rgba(151,25,44,0.12)", border: "2px solid #97192c", borderRadius: "4px", padding: "12px 16px", marginBottom: "20px", fontSize: "13px", color: "#e57373" }}>
          {error}
        </div>
      )}

      {/* Stats row */}
      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "32px" }}>
        <StatCard label="Total Virtual Balance" value={loading ? "—" : `₹${totalBalance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} sub="across all active accounts" accent="#fc920d" />
        <StatCard label="Virtual Accounts" value={loading ? "—" : accounts.length} sub={`${accounts.filter(a => a.is_active).length} active`} accent="#97192c" />
        <StatCard label="Pending Requests" value={loading ? "—" : pending} sub="awaiting approval" accent={pending > 0 ? "#fc920d" : "#1e1e1e"} />
        <StatCard label="Total Requests" value={loading ? "—" : requests.length} sub="last 10 shown below" accent="#1e1e1e" />
      </div>

      {/* Accounts quick list */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "32px" }}>
        {/* Accounts */}
        <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#888" }}>Virtual Accounts</span>
            <Link href="/finance/accounts" style={{ fontSize: "10px", color: "#fc920d", textDecoration: "none", fontWeight: 600, letterSpacing: "0.08em" }}>VIEW ALL →</Link>
          </div>
          {loading ? (
            <div style={{ color: "#333", fontSize: "13px" }}>Loading…</div>
          ) : accounts.length === 0 ? (
            <div style={{ color: "#333", fontSize: "12px" }}>No accounts yet.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {accounts.slice(0, 4).map((a) => (
                <Link key={a.id} href={`/finance/accounts/${a.id}`} style={{ textDecoration: "none" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", border: "2px solid #1e1e1e", borderRadius: "3px", background: "#0d0d0d", cursor: "pointer", transition: "border-color 150ms" }}>
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 600, color: "#ddd" }}>{a.name}</div>
                      <div style={{ fontSize: "10px", color: "#444", marginTop: "2px", fontFamily: "monospace" }}>{a.account_number}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: a.balance_rupees >= 0 ? "#22c55e" : "#ef4444" }}>
                        ₹{a.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </div>
                      <div style={{ fontSize: "9px", color: a.is_active ? "#22c55e" : "#555", textTransform: "uppercase", letterSpacing: "0.1em", marginTop: "2px" }}>
                        {a.is_active ? "active" : "inactive"}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent requests */}
        <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#888" }}>Recent Requests</span>
            <Link href="/finance/requests" style={{ fontSize: "10px", color: "#fc920d", textDecoration: "none", fontWeight: 600, letterSpacing: "0.08em" }}>VIEW ALL →</Link>
          </div>
          {loading ? (
            <div style={{ color: "#333", fontSize: "13px" }}>Loading…</div>
          ) : requests.length === 0 ? (
            <div style={{ color: "#333", fontSize: "12px" }}>No requests yet.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {requests.slice(0, 5).map((r) => {
                const statusColor = r.status === "approved" ? "#22c55e" : r.status === "rejected" ? "#ef4444" : "#fc920d";
                return (
                  <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", border: "2px solid #1e1e1e", borderRadius: "3px", background: "#0d0d0d" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "12px", color: "#ccc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.description}</div>
                      <div style={{ fontSize: "9px", color: "#444", marginTop: "2px" }}>{new Date(r.created_at).toLocaleDateString("en-IN")}</div>
                    </div>
                    <div style={{ textAlign: "right", marginLeft: "12px", flexShrink: 0 }}>
                      <div style={{ fontSize: "12px", fontWeight: 700, color: "#fff" }}>₹{r.amount_rupees.toLocaleString("en-IN")}</div>
                      <div style={{ fontSize: "9px", color: statusColor, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: "2px", fontWeight: 700 }}>{r.status}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Recent Ledger Transactions */}
      <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px", marginBottom: "32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#888" }}>Recent Ledger Transactions</span>
        </div>
        {loading ? (
          <div style={{ color: "#333", fontSize: "13px" }}>Loading transactions…</div>
        ) : transactions.length === 0 ? (
          <div style={{ color: "#333", fontSize: "12px" }}>No transactions logged on the ledger yet.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #222" }}>
                  <th style={{ padding: "8px 12px", fontSize: "10px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em" }}>Date</th>
                  <th style={{ padding: "8px 12px", fontSize: "10px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em" }}>Description</th>
                  <th style={{ padding: "8px 12px", fontSize: "10px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em" }}>Reference</th>
                  <th style={{ padding: "8px 12px", fontSize: "10px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em", textAlign: "right" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(t => {
                  return (
                    <tr key={t.id} style={{ borderBottom: "1px solid #1a1a1a", background: "#0d0d0d" }}>
                      <td style={{ padding: "10px 12px", fontSize: "12px", color: "#888", fontFamily: "monospace" }}>
                        {new Date(t.created_at).toLocaleDateString("en-IN")}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: "12px", color: "#ccc" }}>
                        {t.description}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: "11px", color: "#fc920d", fontFamily: "monospace" }}>
                        {t.reference_type}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: "13px", fontWeight: 700, color: "#fff", textAlign: "right", fontFamily: "monospace" }}>
                        ₹{t.amount_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <div style={{ padding: "12px 16px", border: "2px solid #1e1e1e", borderRadius: "4px", background: "#0d0d0d" }}>
        <p style={{ fontSize: "11px", color: "#333", margin: 0, lineHeight: 1.6 }}>
          <span style={{ color: "#555", fontWeight: 700 }}>IMPORTANT:</span> All balances and transactions in this portal are virtual and for internal tracking only.
          No real money is moved. A single current account (GOBITSNBYTES FOUNDATION) underpins the entire system.
          RazorpayX integration will be wired for real banking operations in a future release.
        </p>
      </div>
    </div>
  );
}
