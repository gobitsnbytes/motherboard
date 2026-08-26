"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API = "";

interface Account { id: string; name: string; description: string | null; balance_rupees: number; balance_paise: number; account_number: string; ifsc: string; is_active: boolean; owner_id: string; created_at: string; }
interface Card { id: string; card_name: string; last_four: string; card_type: string; is_active: boolean; expires_year: string; holder_id: string; }
interface MoneyReq { id: string; amount_rupees: number; status: string; description: string; created_at: string; from_account_id: string | null; to_account_id: string; }
interface Transaction { id: string; source_account_id: string | null; destination_account_id: string | null; amount_rupees: number; amount_paise: number; reference_type: string; reference_id: string | null; description: string; created_at: string; }

const panelClass = "rounded-base border-2 border-border bg-main p-5 shadow-shadow";
const panelTitleClass = "mb-4 font-heading text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [account, setAccount] = useState<Account | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [requests, setRequests] = useState<MoneyReq[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);

  const getHeaders = (): Record<string, string> => ({});

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
      setRequests(Array.isArray(reqs) ? reqs.filter((r: MoneyReq) => r.from_account_id === id || r.to_account_id === id) : []);
      setTransactions(Array.isArray(txs) ? txs : []);
    }).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="font-base text-[13px] text-muted-foreground">Loading…</div>;
  if (!account) return <div className="font-base text-[13px] text-red-500">Account not found.</div>;

  const statusClass = (s: string) =>
    s === "approved" ? "text-green-500" : s === "rejected" ? "text-red-500" : "text-orange";

  const row = (label: string, value: React.ReactNode) => (
    <div className="flex items-center justify-between border-b border-border py-2.5">
      <span className="font-heading text-[11px] uppercase tracking-[0.1em] text-muted-foreground">{label}</span>
      <span className="font-heading text-[13px] text-white/75">{value}</span>
    </div>
  );

  return (
    <div className="font-heading">
      <div className="mb-6">
        <Link href="/finance/accounts" className="font-heading text-[11px] tracking-[0.08em] text-muted-foreground no-underline hover:text-orange">← Accounts</Link>
        <h1 className="m-0 mb-1 mt-2 font-heading text-[22px] font-extrabold text-white">{account.name}</h1>
        {account.description && <p className="font-base text-xs text-muted-foreground">{account.description}</p>}
      </div>

      <div className="mb-7 grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Account info */}
        <div className={panelClass} style={{ boxShadow: "4px 4px 0 0 #fc920d" }}>
          <div className={panelTitleClass}>Account Details</div>
          {row("Account Number", account.account_number.replace(/(\d{4})/g, "$1 ").trim())}
          {row("IFSC", <span className="font-mono">{account.ifsc}</span>)}
          {row("Status", <span className={`font-bold ${account.is_active ? "text-green-500" : "text-muted-foreground"}`}>{account.is_active ? "Active" : "Inactive"}</span>)}
          {row("Created", new Date(account.created_at).toLocaleDateString("en-IN"))}
        </div>

        {/* Balance card */}
        <div className={`${panelClass} flex flex-col items-center justify-center`} style={{ boxShadow: "4px 4px 0 0 #97192c" }}>
          <div className="mb-3 font-heading text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Virtual Balance</div>
          <div className={`font-heading text-[40px] font-black leading-none ${account.balance_rupees >= 0 ? "text-green-500" : "text-red-500"}`}>
            ₹{account.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div className="mt-2.5 font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground/50">
            Paper value only · GOBN0001001
          </div>
        </div>
      </div>

      {/* Cards section */}
      <div className={`${panelClass} mb-5`}>
        <div className="flex items-center justify-between">
          <span className={panelTitleClass}>Virtual Cards ({cards.length})</span>
          <Link href="/finance/cards" className="font-heading text-[10px] font-semibold tracking-[0.08em] text-orange no-underline hover:underline">Manage Cards →</Link>
        </div>
        {cards.length === 0 ? (
          <div className="font-base text-xs text-muted-foreground/50">No cards issued for this account.</div>
        ) : (
          <div className="mt-4 flex flex-wrap gap-3">
            {cards.map(c => (
              <div key={c.id} className="min-w-[180px] rounded-base border-2 border-border bg-background p-4 px-4 shadow-shadow">
                <div className="mb-2 font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{c.card_type} card</div>
                <div className="mb-1.5 font-mono text-sm tracking-[0.15em] text-white/60">•••• •••• •••• {c.last_four}</div>
                <div className="font-base text-[11px] text-muted-foreground">{c.card_name}</div>
                <div className="mt-1.5 font-heading text-[10px] text-muted-foreground/60">Exp: {c.expires_year}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ledger History section */}
      <div className={`${panelClass} mb-5`}>
        <div className={panelTitleClass}>Ledger Transactions</div>
        {transactions.length === 0 ? (
          <div className="font-base text-xs text-muted-foreground/50">No transactions logged on the ledger for this account yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b-2 border-border">
                  <th className="px-3 py-2 font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Date</th>
                  <th className="px-3 py-2 font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Description</th>
                  <th className="px-3 py-2 font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Reference</th>
                  <th className="px-3 py-2 text-right font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(t => {
                  const isInflow = t.destination_account_id === id;
                  return (
                    <tr key={t.id} className="border-b border-border bg-background">
                      <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">
                        {new Date(t.created_at).toLocaleDateString("en-IN")}
                      </td>
                      <td className="px-3 py-2.5 font-base text-xs text-white/75">{t.description}</td>
                      <td className="px-3 py-2.5 font-mono text-[11px] text-orange">{t.reference_type}</td>
                      <td className={`px-3 py-2.5 text-right font-mono text-[13px] font-bold ${isInflow ? "text-green-500" : "text-red-500"}`}>
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
      <div className={panelClass}>
        <div className={panelTitleClass}>Money Requests</div>
        {requests.length === 0 ? (
          <div className="font-base text-xs text-muted-foreground/50">No requests linked to this account.</div>
        ) : (
          <div className="flex flex-col gap-2">
            {requests.map(r => (
              <div key={r.id} className="flex items-center justify-between rounded-base border-2 border-border bg-background px-3.5 py-2.5">
                <div>
                  <div className="font-base text-[13px] text-white/75">{r.description}</div>
                  <div className="mt-0.5 font-heading text-[10px] text-muted-foreground/60">
                    {new Date(r.created_at).toLocaleDateString("en-IN")} · {r.from_account_id ? "transfer" : "pool draw"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-heading text-sm font-bold text-white">₹{r.amount_rupees.toLocaleString("en-IN")}</div>
                  <div className={`mt-0.5 font-heading text-[9px] font-bold uppercase tracking-[0.08em] ${statusClass(r.status)}`}>{r.status}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
