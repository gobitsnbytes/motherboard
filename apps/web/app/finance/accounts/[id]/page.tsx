"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Account { id: string; name: string; description: string | null; balance_rupees: number; balance_paise: number; account_number: string; ifsc: string; is_active: boolean; owner_id: string; created_at: string; }
interface Card { id: string; card_name: string; last_four: string; card_type: string; is_active: boolean; expires_year: string; holder_id: string; }
interface MoneyReq { id: string; amount_rupees: number; status: string; description: string; created_at: string; from_account_id: string | null; }
interface Transaction { id: string; source_account_id: string | null; destination_account_id: string | null; amount_rupees: number; amount_paise: number; reference_type: string; reference_id: string | null; description: string; created_at: string; }

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [account, setAccount] = useState<Account | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [requests, setRequests] = useState<MoneyReq[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);

  const getHeaders = (): Record<string, string> => {
    const uid = typeof window !== "undefined" ? localStorage.getItem("x-user-id") : null;
    return uid ? { "X-User-Id": uid } : {};
  };

  useEffect(() => {
    if (!id) return;
    const h = getHeaders();
    Promise.all([
      fetch(`${API}/api/finance/accounts/${id}`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/finance/accounts/${id}/cards`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/finance/requests`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/finance/accounts/${id}/transactions`, { headers: h }).then(r => r.json()),
    ]).then(([acc, cds, reqs, txs]) => {
      setAccount(acc);
      setCards(Array.isArray(cds) ? cds : []);
      setRequests(Array.isArray(reqs) ? reqs.filter((r: MoneyReq) => r.from_account_id === id || (reqs as MoneyReq[]).find(x => x.id === r.id)) : []);
      setTransactions(Array.isArray(txs) ? txs : []);
    }).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div style={{ fontFamily: "Inter, sans-serif", color: "#555", fontSize: "13px" }}>Loading…</div>;
  if (!account) return <div style={{ fontFamily: "Inter, sans-serif", color: "#ef4444", fontSize: "13px" }}>Account not found.</div>;

  const statusColor = (s: string) => s === "approved" ? "#22c55e" : s === "rejected" ? "#ef4444" : "#fc920d";

  const row = (label: string, value: React.ReactNode) => (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid #1a1a1a" }}>
      <span style={{ fontSize: "11px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em" }}>{label}</span>
      <span style={{ fontSize: "13px", color: "#ccc", fontFamily: typeof value === "string" && value.match(/^\d/) ? "monospace" : "Inter, sans-serif" }}>{value}</span>
    </div>
  );

  return (
    <div style={{ fontFamily: "Inter, sans-serif" }}>
      <div style={{ marginBottom: "24px" }}>
        <Link href="/finance/accounts" style={{ fontSize: "11px", color: "#555", textDecoration: "none", letterSpacing: "0.08em" }}>← Accounts</Link>
        <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#fff", margin: "8px 0 4px" }}>{account.name}</h1>
        {account.description && <p style={{ fontSize: "12px", color: "#555" }}>{account.description}</p>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "28px" }}>
        {/* Account info */}
        <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px", boxShadow: "4px 4px 0 0 #fc920d" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "14px" }}>Account Details</div>
          {row("Account Number", account.account_number.replace(/(\d{4})/g, "$1 ").trim())}
          {row("IFSC", account.ifsc)}
          {row("Status", <span style={{ color: account.is_active ? "#22c55e" : "#555", fontWeight: 700 }}>{account.is_active ? "Active" : "Inactive"}</span>)}
          {row("Created", new Date(account.created_at).toLocaleDateString("en-IN"))}
        </div>

        {/* Balance card */}
        <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px", boxShadow: "4px 4px 0 0 #97192c", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
          <div style={{ fontSize: "10px", color: "#555", textTransform: "uppercase", letterSpacing: "0.15em", marginBottom: "12px" }}>Virtual Balance</div>
          <div style={{ fontSize: "40px", fontWeight: 900, color: account.balance_rupees >= 0 ? "#22c55e" : "#ef4444", lineHeight: 1 }}>
            ₹{account.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "10px", color: "#333", marginTop: "10px" }}>Paper value only · GOBN0001001</div>
        </div>
      </div>

      {/* Cards section */}
      <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px", marginBottom: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <span style={{ fontSize: "11px", fontWeight: 700, color: "#888", textTransform: "uppercase", letterSpacing: "0.12em" }}>Virtual Cards ({cards.length})</span>
          <Link href="/finance/cards" style={{ fontSize: "10px", color: "#fc920d", textDecoration: "none", fontWeight: 600 }}>Manage Cards →</Link>
        </div>
        {cards.length === 0 ? (
          <div style={{ fontSize: "12px", color: "#333" }}>No cards issued for this account.</div>
        ) : (
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            {cards.map(c => (
              <div key={c.id} style={{ background: "#0d0d0d", border: "2px solid #2a2a2a", borderRadius: "4px", padding: "14px 16px", minWidth: "180px", boxShadow: "3px 3px 0 0 #1e1e1e" }}>
                <div style={{ fontSize: "10px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "8px" }}>{c.card_type} card</div>
                <div style={{ fontFamily: "monospace", fontSize: "14px", color: "#aaa", letterSpacing: "0.15em", marginBottom: "6px" }}>•••• •••• •••• {c.last_four}</div>
                <div style={{ fontSize: "11px", color: "#666" }}>{c.card_name}</div>
                <div style={{ fontSize: "10px", color: "#444", marginTop: "6px" }}>Exp: {c.expires_year}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ledger History section */}
      <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px", marginBottom: "20px" }}>
        <div style={{ fontSize: "11px", fontWeight: 700, color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "16px" }}>Ledger Transactions</div>
        {transactions.length === 0 ? (
          <div style={{ fontSize: "12px", color: "#333" }}>No transactions logged on the ledger for this account yet.</div>
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
                  const isInflow = t.destination_account_id === id;
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
                      <td style={{ padding: "10px 12px", fontSize: "13px", fontWeight: 700, color: isInflow ? "#22c55e" : "#ef4444", textAlign: "right", fontFamily: "monospace" }}>
                        {isInflow ? "+" : "-"}₹{t.amount_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Requests section */}
      <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px" }}>
        <div style={{ fontSize: "11px", fontWeight: 700, color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "16px" }}>Money Requests</div>
        {requests.length === 0 ? (
          <div style={{ fontSize: "12px", color: "#333" }}>No requests linked to this account.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {requests.map(r => (
              <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", border: "2px solid #1a1a1a", borderRadius: "3px", background: "#0d0d0d" }}>
                <div>
                  <div style={{ fontSize: "13px", color: "#ccc" }}>{r.description}</div>
                  <div style={{ fontSize: "10px", color: "#444", marginTop: "2px" }}>{new Date(r.created_at).toLocaleDateString("en-IN")} · {r.from_account_id ? "transfer" : "pool draw"}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#fff" }}>₹{r.amount_rupees.toLocaleString("en-IN")}</div>
                  <div style={{ fontSize: "9px", color: statusColor(r.status), textTransform: "uppercase", fontWeight: 700, marginTop: "2px" }}>{r.status}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
