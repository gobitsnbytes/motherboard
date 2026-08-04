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
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-base border-2 border-border bg-[#97192C] p-6 text-white shadow-shadow">
        <div>
          <div className="flex items-center gap-2">
            <Coins className="size-6 text-[#FC920D]" />
            <h1 className="font-heading font-extrabold text-2xl tracking-wide">
              Financial Operations &amp; Ledger
            </h1>
          </div>
          <p className="mt-1 text-xs text-white/80 font-base">
            RazorpayX banking integration &amp; virtual ledger accounts for GOBITSNBYTES FOUNDATION.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={fetchFinanceData}
            variant="neutral"
            className="border-2 border-border bg-[#111] text-white hover:bg-[#222]"
          >
            <RefreshCw className={`size-4 mr-1.5 ${loading ? "animate-spin text-[#FC920D]" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-base border-2 border-[#97192C] bg-[#97192C]/10 p-4 text-xs font-bold text-red-200 shadow-shadow">
          <AlertCircle className="size-5 shrink-0 text-[#97192C]" />
          <span>{error}</span>
        </div>
      )}

      {/* Quick Stats Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Total Virtual Balance
            </CardTitle>
            <Coins className="size-4 text-[#FC920D]" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-28" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                ₹{totalBalance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Across all active accounts</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Virtual Accounts
            </CardTitle>
            <CreditCard className="size-4 text-[#97192C]" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {accounts.length}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">
              {accounts.filter((a) => a.is_active).length} active ledger nodes
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Pending Requests
            </CardTitle>
            <Clock className="size-4 text-[#FC920D]" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="font-heading font-black text-2xl text-foreground">
                {pendingRequests.length}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Awaiting dual authorization</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-heading font-bold uppercase tracking-wider text-muted-foreground">
              Compliance Status
            </CardTitle>
            <ShieldCheck className="size-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="success">Section 8 Verified</Badge>
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">Zero informal UPI routing</p>
          </CardContent>
        </Card>
      </div>

      {/* Responsive 2-Column Main Section */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left Column: Virtual Accounts */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <Building2 className="size-5 text-[#FC920D]" />
              <CardTitle className="font-heading font-bold text-base">Virtual Accounts</CardTitle>
            </div>
            <Badge variant="neutral" className="border-border font-mono text-[10px]">
              RazorpayX Sync
            </Badge>
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
                icon={<CreditCard className="size-8 text-muted-foreground" />}
                title="No virtual accounts initialized"
                description="Connect RazorpayX credentials or seed virtual ledger accounts via backend CLI."
              />
            ) : (
              <div className="space-y-3">
                {accounts.map((acc) => (
                  <div
                    key={acc.id}
                    className="flex items-center justify-between rounded-base border-2 border-border bg-[#111] p-3 text-white transition-all hover:translate-x-[2px] hover:translate-y-[2px]"
                  >
                    <div>
                      <div className="font-heading font-bold text-sm text-white">{acc.name}</div>
                      <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                        Acc: {acc.account_number}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-heading font-bold text-sm text-[#FC920D]">
                        ₹{acc.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </div>
                      <Badge variant={acc.is_active ? "success" : "neutral"} className="mt-1">
                        {acc.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: Recent Money Requests & Payouts */}
        <Card className="border-2 border-border shadow-shadow">
          <CardHeader className="flex flex-row items-center justify-between border-b-2 border-border pb-4">
            <div className="flex items-center gap-2">
              <FileText className="size-5 text-[#97192C]" />
              <CardTitle className="font-heading font-bold text-base">Disbursement Requests</CardTitle>
            </div>
            <Badge variant="neutral" className="border-border font-mono text-[10px]">
              Dual Approval Required
            </Badge>
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
                icon={<Coins className="size-8 text-muted-foreground" />}
                title="No active disbursement requests"
                description="All submitted reimbursement and payout requests will appear here."
              />
            ) : (
              <div className="space-y-3">
                {requests.map((req) => (
                  <div
                    key={req.id}
                    className="flex items-center justify-between rounded-base border-2 border-border bg-[#111] p-3 text-white transition-all"
                  >
                    <div>
                      <div className="font-heading font-bold text-sm text-white">{req.description}</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        Submitted {new Date(req.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-heading font-bold text-sm text-white">
                        ₹{req.amount_rupees.toLocaleString("en-IN")}
                      </div>
                      <Badge
                        variant={req.status === "approved" ? "success" : req.status === "pending" ? "warning" : "danger"}
                        className="mt-1"
                      >
                        {req.status}
                      </Badge>
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
