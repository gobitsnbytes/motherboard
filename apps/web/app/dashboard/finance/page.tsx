"use client";

import React, { useEffect, useState } from "react";
import {
  Coins,
  CreditCard,
  TrendingUp,
  ArrowUpRight,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Building2,
  FileText,
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
import EmptyState from "components/dashboard/EmptyState";

interface Account {
  id: string;
  name: string;
  balance_rupees: number;
  is_active: boolean;
  account_number: string;
}

interface MoneyReq {
  id: string;
  amount_rupees: number;
  status: string;
  description: string;
  created_at: string;
}

interface Transaction {
  id: string;
  source_account_id: string | null;
  destination_account_id: string | null;
  amount_rupees: number;
  amount_paise: number;
  reference_type: string;
  reference_id: string | null;
  description: string;
  created_at: string;
}

export default function DashboardFinancePage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [requests, setRequests] = useState<MoneyReq[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFinanceData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [accRes, reqRes, txRes] = await Promise.all([
        fetch("/api/finance/accounts").catch(() => null),
        fetch("/api/finance/requests?limit=10").catch(() => null),
        fetch("/api/finance/transactions?limit=6").catch(() => null),
      ]);

      const accs = accRes && accRes.ok ? await accRes.json() : [];
      const reqs = reqRes && reqRes.ok ? await reqRes.json() : [];
      const txs = txRes && txRes.ok ? await txRes.json() : [];

      setAccounts(Array.isArray(accs) ? accs : []);
      setRequests(Array.isArray(reqs) ? reqs : []);
      setTransactions(Array.isArray(txs) ? txs : []);
    } catch (err) {
      console.error(err);
      setError("Unable to connect to financial ledger backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFinanceData();
  }, []);

  const totalBalance = accounts.reduce((sum, a) => sum + (a.balance_rupees || 0), 0);
  const pendingRequests = requests.filter((r) => r.status === "pending");

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-base border-2 border-border bg-main p-5 text-main-foreground shadow-dark">
        <div>
          <div className="flex items-center gap-2">
            <Coins className="size-6 text-orange" />
            <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight uppercase">
              Financial Operations &amp; Ledger
            </h1>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-main-foreground/80 font-base">
            RazorpayX banking integration &amp; virtual ledger accounts for GOBITSNBYTES FOUNDATION.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchFinanceData}
            className="flex items-center gap-1.5 px-4 py-2 font-mono font-bold text-xs uppercase rounded-base border-2 border-border bg-secondary-background text-foreground hover:bg-orange hover:text-black shadow-light hover:translate-x-[1px] hover:translate-y-[1px] transition-all"
          >
            <RefreshCw className={`size-3.5 mr-1 ${loading ? "animate-spin text-orange" : "text-orange"}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-base border-2 border-red-700 bg-red-50 p-4 text-xs font-mono font-bold text-red-900 shadow-light">
          <AlertCircle className="size-5 shrink-0 text-red-700" />
          <span>{error}</span>
        </div>
      )}

      {/* Quick Stats Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Total Virtual Balance
            </CardTitle>
            <Coins className="size-4 text-orange" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-28" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                ₹{totalBalance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
            )}
            <p className="text-[11px] font-mono text-muted-foreground mt-1">Across all active accounts</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Virtual Accounts
            </CardTitle>
            <CreditCard className="size-4 text-orange" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {accounts.length}
              </div>
            )}
            <p className="text-[11px] font-mono text-muted-foreground mt-1">
              {accounts.filter((a) => a.is_active).length} active ledger nodes
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Pending Requests
            </CardTitle>
            <Clock className="size-4 text-amber-400" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {pendingRequests.length}
              </div>
            )}
            <p className="text-[11px] font-mono text-muted-foreground mt-1">Awaiting dual authorization</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-secondary-background shadow-light">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Governance checks
            </CardTitle>
            <ShieldCheck className="size-4 text-emerald-400" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 mt-1">
              <span className="border-2 border-emerald-700 bg-emerald-50 text-emerald-900 px-2 py-0.5 text-[10px] font-mono font-bold rounded-base shadow-light">
                Policy configured
              </span>
            </div>
            <p className="text-[11px] font-mono text-muted-foreground mt-2">No informal UPI routing configured</p>
          </CardContent>
        </Card>
      </div>

      {/* Responsive 2-Column Main Section */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left Column: Virtual Accounts */}
        <Card className="border-2 border-border bg-secondary-background shadow-dark rounded-base">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border bg-muted pb-3.5">
            <div className="flex items-center gap-2">
              <Building2 className="size-4 text-orange" />
              <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-foreground">Virtual Accounts</CardTitle>
            </div>
            <span className="border border-border bg-secondary-background text-muted-foreground font-mono text-[10px] px-2 py-0.5 rounded-base">
              RazorpayX Sync
            </span>
          </CardHeader>
          <CardContent className="pt-4">
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : accounts.length === 0 ? (
              <EmptyState
                icon={<CreditCard className="size-8 text-zinc-600" />}
                title="No virtual accounts initialized"
                description="Connect RazorpayX credentials or seed virtual ledger accounts via backend CLI."
              />
            ) : (
              <div className="space-y-3">
                {accounts.map((acc) => (
                  <div
                    key={acc.id}
                    className="flex items-center justify-between rounded-base border-2 border-border bg-muted p-3.5 text-foreground transition-all hover:translate-x-[2px] hover:translate-y-[2px] shadow-light"
                  >
                    <div>
                      <div className="font-heading font-black text-sm text-foreground uppercase">{acc.name}</div>
                      <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                        Acc: {acc.account_number}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold text-sm text-orange">
                        ₹{acc.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </div>
                      <span className={`inline-block mt-1 px-2 py-0.5 text-[10px] font-mono font-bold rounded-base border ${acc.is_active ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-zinc-800 text-zinc-400 border-zinc-700"}`}>
                        {acc.is_active ? "Active" : "Disabled"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: Recent Money Requests & Payouts */}
        <Card className="border-2 border-border bg-secondary-background shadow-dark rounded-base">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border bg-muted pb-3.5">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-orange" />
              <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-foreground">Disbursement Requests</CardTitle>
            </div>
            <span className="border border-border bg-secondary-background text-muted-foreground font-mono text-[10px] px-2 py-0.5 rounded-base">
              Dual Approval Required
            </span>
          </CardHeader>
          <CardContent className="pt-4">
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : requests.length === 0 ? (
              <EmptyState
                icon={<Coins className="size-8 text-zinc-600" />}
                title="No active disbursement requests"
                description="All submitted reimbursement and payout requests will appear here."
              />
            ) : (
              <div className="space-y-3">
                {requests.map((req) => (
                  <div
                    key={req.id}
                    className="flex items-center justify-between rounded-base border-2 border-border bg-muted p-3.5 text-foreground transition-all shadow-light"
                  >
                    <div>
                      <div className="font-heading font-black text-sm text-foreground">{req.description}</div>
                      <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                        Submitted {new Date(req.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold text-sm text-foreground">
                        ₹{req.amount_rupees.toLocaleString("en-IN")}
                      </div>
                      <span
                        className={`inline-block mt-1 px-2 py-0.5 text-[10px] font-mono font-bold rounded-base border ${
                          req.status === "approved" ? "bg-emerald-950 text-emerald-400 border-emerald-800" :
                          req.status === "pending" ? "bg-amber-950 text-amber-400 border-amber-800" :
                          "bg-red-950 text-red-400 border-red-800"
                        }`}
                      >
                        {req.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
