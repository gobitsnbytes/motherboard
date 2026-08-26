"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";

const API = "";

interface Account { id: string; name: string; balance_rupees: number; is_active: boolean; account_number: string; }
interface MoneyReq { id: string; amount_rupees: number; status: string; description: string; created_at: string; }
interface Transaction { id: string; source_account_id: string | null; destination_account_id: string | null; amount_rupees: number; amount_paise: number; reference_type: string; reference_id: string | null; description: string; created_at: string; }
interface ComplianceRule { rule: string; status?: string; citation?: string; }
interface Compliance {
  foundation_name: string;
  licence_number: string;
  current_fy: string;
  cash_collection_prohibited: boolean;
  personal_upi_routing_prohibited: boolean;
  local_bank_accounts_prohibited: boolean;
  sponsorship_flows_upstream_first: boolean;
  dual_auth_threshold_paise: number;
  dual_auth_enabled: boolean;
  fy_start_month: number;
  open_requests_above_threshold: number;
  overall_status: "compliant" | "warning";
  rules: ComplianceRule[];
}

function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-w-[160px] flex-1 rounded-base border-2 border-border bg-main px-[22px] py-5 shadow-shadow"
      style={accent ? { boxShadow: `4px 4px 0 0 ${accent}` } : undefined}
    >
      <div className="mb-2.5 font-heading text-[10px] uppercase tracking-[0.15em] text-muted-foreground">{label}</div>
      <div className="font-heading text-[28px] font-extrabold leading-none text-white">{value}</div>
      {sub && <div className="mt-1.5 font-heading text-[11px] text-muted-foreground/70">{sub}</div>}
    </motion.div>
  );
}

function ComplianceRow({ label, pass }: { label: string; pass: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-base border-2 border-border bg-background px-3 py-2">
      <span className="font-base text-xs text-foreground/80">{label}</span>
      <span
        className={`shrink-0 rounded-base border-2 px-1.5 py-0.5 font-heading text-[9px] font-bold uppercase tracking-[0.08em] ${
          pass
            ? "border-green-600 bg-green-500/15 text-green-400"
            : "border-yellow-600 bg-yellow-500/15 text-yellow-400"
        }`}
      >
        {pass ? "PASS" : "WARN"}
      </span>
    </div>
  );
}

export default function FinanceDashboard() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [requests, setRequests] = useState<MoneyReq[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [compliance, setCompliance] = useState<Compliance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/finance/accounts`).then((r) => r.json()),
      fetch(`${API}/api/finance/requests?limit=10`).then((r) => r.json()),
      fetch(`${API}/api/finance/transactions?limit=6`).then((r) => r.json()),
      fetch(`${API}/api/finance/compliance`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ])
      .then(([accs, reqs, txs, comp]) => {
        setAccounts(Array.isArray(accs) ? accs : []);
        setRequests(Array.isArray(reqs) ? reqs : []);
        setTransactions(Array.isArray(txs) ? txs : []);
        setCompliance(comp);
      })
      .catch(() => setError("Could not load finance data. Check API connection."))
      .finally(() => setLoading(false));
  }, []);

  const totalBalance = accounts.reduce((s, a) => s + a.balance_rupees, 0);
  const pending = requests.filter((r) => r.status === "pending").length;

  return (
    <div className="font-heading">
      {/* Page title */}
      <div className="mb-7">
        <h1 className="m-0 font-heading text-[22px] font-extrabold tracking-[-0.01em] text-white">Dashboard</h1>
        <p className="mt-1 font-base text-xs text-muted-foreground">
          Virtual ledger overview · all balances are internal paper values
        </p>
      </div>

      {error && (
        <div className="mb-5 rounded-base border-2 border-burgundy bg-burgundy/10 px-4 py-3 font-base text-[13px] text-red-300 shadow-shadow">
          {error}
        </div>
      )}

      {/* Stats row */}
      <div className="mb-8 flex flex-wrap gap-4">
        <StatCard label="Total Virtual Balance" value={loading ? "—" : `₹${totalBalance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} sub="across all active accounts" accent="#fc920d" />
        <StatCard label="Virtual Accounts" value={loading ? "—" : accounts.length} sub={`${accounts.filter(a => a.is_active).length} active`} accent="#97192c" />
        <StatCard label="Pending Requests" value={loading ? "—" : pending} sub="awaiting approval" accent={pending > 0 ? "#fc920d" : undefined} />
        <StatCard label="Total Requests" value={loading ? "—" : requests.length} sub="last 10 shown below" />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Accounts */}
        <div className="rounded-base border-2 border-border bg-main p-5 shadow-shadow">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-heading text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Virtual Accounts</span>
            <Link href="/finance/accounts" className="font-heading text-[10px] font-semibold tracking-[0.08em] text-orange no-underline hover:underline">VIEW ALL →</Link>
          </div>
          {loading ? (
            <div className="font-base text-[13px] text-muted-foreground/50">Loading…</div>
          ) : accounts.length === 0 ? (
            <div className="font-base text-xs text-muted-foreground/50">No accounts yet.</div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {accounts.slice(0, 4).map((a) => (
                <Link key={a.id} href={`/finance/accounts/${a.id}`} className="no-underline">
                  <div className="flex cursor-pointer items-center justify-between rounded-base border-2 border-border bg-background px-3 py-2.5 transition-colors duration-150 hover:border-orange">
                    <div>
                      <div className="font-heading text-[13px] font-semibold text-white/85">{a.name}</div>
                      <div className="mt-0.5 font-mono text-[10px] text-muted-foreground/60">{a.account_number}</div>
                    </div>
                    <div className="text-right">
                      <div className={`font-heading text-[13px] font-bold ${a.balance_rupees >= 0 ? "text-green-500" : "text-red-500"}`}>
                        ₹{a.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </div>
                      <div className={`mt-0.5 font-heading text-[9px] uppercase tracking-[0.1em] ${a.is_active ? "text-green-500" : "text-muted-foreground"}`}>
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
        <div className="rounded-base border-2 border-border bg-main p-5 shadow-shadow">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-heading text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Recent Requests</span>
            <Link href="/finance/requests" className="font-heading text-[10px] font-semibold tracking-[0.08em] text-orange no-underline hover:underline">VIEW ALL →</Link>
          </div>
          {loading ? (
            <div className="font-base text-[13px] text-muted-foreground/50">Loading…</div>
          ) : requests.length === 0 ? (
            <div className="font-base text-xs text-muted-foreground/50">No requests yet.</div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {requests.slice(0, 5).map((r) => {
                const statusColor = r.status === "approved" ? "text-green-500" : r.status === "rejected" ? "text-red-500" : "text-orange";
                return (
                  <div key={r.id} className="flex items-center justify-between rounded-base border-2 border-border bg-background px-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-base text-xs text-white/75">{r.description}</div>
                      <div className="mt-0.5 font-heading text-[9px] text-muted-foreground/60">{new Date(r.created_at).toLocaleDateString("en-IN")}</div>
                    </div>
                    <div className="ml-3 shrink-0 text-right">
                      <div className="font-heading text-xs font-bold text-white">₹{r.amount_rupees.toLocaleString("en-IN")}</div>
                      <div className={`mt-0.5 font-heading text-[9px] font-bold uppercase tracking-[0.08em] ${statusColor}`}>{r.status}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Section 8 Status */}
        <div className="rounded-base border-2 border-border bg-main p-5 shadow-shadow lg:col-span-1">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-heading text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Section 8 Status</span>
            {compliance && (
              <span
                className={`rounded-base border-2 px-1.5 py-0.5 font-heading text-[9px] font-bold uppercase tracking-[0.08em] ${
                  compliance.overall_status === "compliant"
                    ? "border-green-600 bg-green-500/15 text-green-400"
                    : "border-yellow-600 bg-yellow-500/15 text-yellow-400"
                }`}
              >
                {compliance.overall_status}
              </span>
            )}
          </div>
          {!compliance ? (
            <div className="font-base text-xs text-muted-foreground/50">
              {loading ? "Loading compliance…" : "Compliance disclosure unavailable."}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <ComplianceRow label="No cash collections" pass={compliance.cash_collection_prohibited} />
              <ComplianceRow label="No personal UPI routing" pass={compliance.personal_upi_routing_prohibited} />
              <ComplianceRow label="No informal bank accounts" pass={compliance.local_bank_accounts_prohibited} />
              <ComplianceRow label="Sponsorships flow upstream-first" pass={compliance.sponsorship_flows_upstream_first} />
              <div className="mt-1 flex items-center justify-between rounded-base border-2 border-border bg-background px-3 py-2">
                <span className="font-base text-xs text-foreground/80">
                  Dual auth ≥ ₹{(compliance.dual_auth_threshold_paise / 100).toLocaleString("en-IN")}
                </span>
                <span className={`font-heading text-[9px] font-bold uppercase tracking-[0.08em] ${compliance.dual_auth_enabled ? "text-green-400" : "text-yellow-400"}`}>
                  {compliance.dual_auth_enabled ? "ENFORCED" : "OFF"}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-base border-2 border-border bg-background px-3 py-2">
                <span className="font-base text-xs text-foreground/80">Open commitments above band</span>
                <span className={`font-heading text-[11px] font-bold ${compliance.open_requests_above_threshold > 0 ? "text-orange" : "text-green-400"}`}>
                  {compliance.open_requests_above_threshold}
                </span>
              </div>
              <div className="mt-1 font-heading text-[10px] uppercase tracking-[0.1em] text-muted-foreground/70">
                FY {compliance.current_fy} · Licence No. 186266
              </div>
            </div>
          )}
        </div>

        {/* Recent Ledger Transactions */}
        <div className="rounded-base border-2 border-border bg-main p-5 shadow-shadow lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-heading text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground">Recent Ledger Transactions</span>
          </div>
          {loading ? (
            <div className="font-base text-[13px] text-muted-foreground/50">Loading transactions…</div>
          ) : transactions.length === 0 ? (
            <div className="font-base text-xs text-muted-foreground/50">No transactions logged on the ledger yet.</div>
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
                  {transactions.map(t => (
                    <tr key={t.id} className="border-b border-border bg-background">
                      <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">
                        {new Date(t.created_at).toLocaleDateString("en-IN")}
                      </td>
                      <td className="px-3 py-2.5 font-base text-xs text-white/75">{t.description}</td>
                      <td className="px-3 py-2.5 font-mono text-[11px] text-orange">{t.reference_type}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-[13px] font-bold text-white">
                        ₹{t.amount_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="rounded-base border-2 border-border bg-background px-4 py-3">
        <p className="m-0 font-base text-[11px] leading-relaxed text-muted-foreground/60">
          <span className="font-heading font-bold text-muted-foreground">IMPORTANT:</span> All balances and transactions in this portal are virtual and for internal tracking only.
          No real money is moved. A single current account (GOBITSNBYTES FOUNDATION) underpins the entire system.
          RazorpayX integration will be wired for real banking operations in a future release.
        </p>
      </div>
    </div>
  );
}
