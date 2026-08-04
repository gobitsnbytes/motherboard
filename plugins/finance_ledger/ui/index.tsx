"use client";

import React, { useEffect, useState } from "react";
import { Landmark, RefreshCw, CheckCircle2, ArrowUpRight, DollarSign, Wallet, FileText, Plus, ShieldAlert } from "lucide-react";

interface JournalEntry {
  id: string;
  transaction_date: string;
  memo: string;
  debit_account: string;
  credit_account: string;
  amount: number;
  status: string;
}

interface VirtualAccount {
  account_id: string;
  fork_city: string;
  department: string;
  balance: number;
  upi_id: string;
  status: string;
}

interface Expense {
  expense_id: string;
  submitter_name: string;
  department: string;
  category: string;
  amount: number;
  status: string;
  receipt_url?: string;
  created_at: string;
  approver_note?: string;
}

interface Summary {
  total_assets: number;
  total_journal_entries: number;
  total_debits: number;
  total_credits: number;
  is_balanced: boolean;
  virtual_accounts_count: number;
  virtual_accounts_total_balance: number;
  pending_expenses_count: number;
}

export default function FinanceLedgerUI() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [accounts, setAccounts] = useState<VirtualAccount[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"journal" | "accounts" | "expenses">("journal");
  
  // Modals state
  const [showJournalModal, setShowJournalModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);

  // Forms
  const [journalForm, setJournalForm] = useState({
    memo: "",
    debit_account: "Expense:Events",
    credit_account: "Bank:RazorpayX",
    amount: 5000,
  });

  const [accountForm, setAccountForm] = useState({
    fork_city: "",
    department: "Events & Logistics",
    initial_balance: 25000,
  });

  const fetchFinanceData = async () => {
    setLoading(true);
    try {
      const [entriesRes, accountsRes, expensesRes, summaryRes] = await Promise.all([
        fetch("/api/plugins/finance_ledger/journal-entries"),
        fetch("/api/plugins/finance_ledger/virtual-accounts"),
        fetch("/api/plugins/finance_ledger/expenses"),
        fetch("/api/plugins/finance_ledger/summary"),
      ]);

      if (entriesRes.ok) setEntries(await entriesRes.json());
      if (accountsRes.ok) setAccounts(await accountsRes.json());
      if (expensesRes.ok) setExpenses(await expensesRes.json());
      if (summaryRes.ok) setSummary(await summaryRes.json());
    } catch (err) {
      console.error("Failed to load finance ledger data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFinanceData();
  }, []);

  const handleCreateJournal = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/plugins/finance_ledger/journal-entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(journalForm),
      });
      if (res.ok) {
        setShowJournalModal(false);
        setJournalForm({ memo: "", debit_account: "Expense:Events", credit_account: "Bank:RazorpayX", amount: 5000 });
        await fetchFinanceData();
      }
    } catch (err) {
      console.error("Journal creation failed", err);
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/plugins/finance_ledger/virtual-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(accountForm),
      });
      if (res.ok) {
        setShowAccountModal(false);
        setAccountForm({ fork_city: "", department: "Events & Logistics", initial_balance: 25000 });
        await fetchFinanceData();
      }
    } catch (err) {
      console.error("Account allocation failed", err);
    }
  };

  const handleReviewExpense = async (expenseId: string, approved: boolean) => {
    try {
      const res = await fetch(`/api/plugins/finance_ledger/expenses/${expenseId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, note: approved ? "Approved by CFO" : "Rejected" }),
      });
      if (res.ok) {
        await fetchFinanceData();
      }
    } catch (err) {
      console.error("Expense review failed", err);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 border-4 border-border bg-main/5 rounded-base shadow-light">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center p-3 border-2 border-border bg-main rounded-base text-main-foreground shadow-light">
            <Landmark className="size-6" />
          </div>
          <div>
            <h2 className="text-xl font-heading font-bold text-foreground">
              Section 8 Finance Ledger & RazorpayX Vault
            </h2>
            <p className="text-xs text-muted-foreground font-base mt-0.5">
              Double-entry Section 8 ledger, virtual account allocation, and expense approval routing.
            </p>
          </div>
        </div>

        <button
          onClick={fetchFinanceData}
          disabled={loading}
          className="flex items-center gap-2 border-2 border-border bg-bg text-foreground px-3.5 py-2 text-xs font-bold rounded-base hover:bg-main/10 transition-all"
        >
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
          Sync Ledger
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Total Liquid Assets</span>
            <Wallet className="size-4 text-green-500" />
          </div>
          <div className="text-2xl font-heading font-extrabold text-foreground mt-2 font-mono">
            ₹{summary ? summary.total_assets.toLocaleString("en-IN") : "-"}
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Double-Entry Balance</span>
            <CheckCircle2 className="size-4 text-green-500" />
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xl font-heading font-extrabold text-foreground font-mono">
              ₹{summary ? summary.total_debits.toLocaleString("en-IN") : "-"}
            </span>
            <span className="px-2 py-0.5 text-[10px] font-bold border border-border bg-green-500/20 text-green-700 rounded-base">
              BALANCED ✓
            </span>
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Virtual Accounts</span>
            <Landmark className="size-4 text-main" />
          </div>
          <div className="text-2xl font-heading font-extrabold text-foreground mt-2 font-mono">
            {summary ? summary.virtual_accounts_count : "-"} Accounts
          </div>
        </div>

        <div className="border-4 border-border bg-bg p-4 rounded-base shadow-light">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase">
            <span>Pending Expenses</span>
            <ShieldAlert className="size-4 text-amber-500" />
          </div>
          <div className="text-2xl font-heading font-extrabold text-foreground mt-2 font-mono">
            {summary ? summary.pending_expenses_count : "-"} Claims
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b-2 border-border gap-2">
        <button
          onClick={() => setActiveTab("journal")}
          className={`px-4 py-2 font-heading font-bold text-xs border-t-2 border-x-2 rounded-t-base ${
            activeTab === "journal" ? "border-border bg-bg text-foreground" : "border-transparent text-muted-foreground"
          }`}
        >
          Double-Entry Journal ({entries.length})
        </button>
        <button
          onClick={() => setActiveTab("accounts")}
          className={`px-4 py-2 font-heading font-bold text-xs border-t-2 border-x-2 rounded-t-base ${
            activeTab === "accounts" ? "border-border bg-bg text-foreground" : "border-transparent text-muted-foreground"
          }`}
        >
          Virtual Accounts ({accounts.length})
        </button>
        <button
          onClick={() => setActiveTab("expenses")}
          className={`px-4 py-2 font-heading font-bold text-xs border-t-2 border-x-2 rounded-t-base ${
            activeTab === "expenses" ? "border-border bg-bg text-foreground" : "border-transparent text-muted-foreground"
          }`}
        >
          Expense Routing ({expenses.length})
        </button>
      </div>

      {/* Tab 1: Double-Entry Journal */}
      {activeTab === "journal" && (
        <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light overflow-x-auto">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider">
              General Ledger Transactions
            </h3>
            <button
              onClick={() => setShowJournalModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold border-2 border-border bg-main text-main-foreground rounded-base shadow-light"
            >
              <Plus className="size-4" /> New Entry
            </button>
          </div>

          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-border bg-main/10 font-heading text-foreground">
                <th className="p-3">Entry ID / Date</th>
                <th className="p-3">Memo</th>
                <th className="p-3">Debit Account</th>
                <th className="p-3">Credit Account</th>
                <th className="p-3 text-right">Amount (INR)</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-b border-border/50 hover:bg-main/5 font-mono">
                  <td className="p-3 font-bold text-foreground">
                    <div>{entry.id}</div>
                    <div className="text-[10px] text-muted-foreground">{entry.transaction_date.slice(0, 10)}</div>
                  </td>
                  <td className="p-3 font-sans font-medium text-foreground">{entry.memo}</td>
                  <td className="p-3 text-green-700 font-bold">{entry.debit_account}</td>
                  <td className="p-3 text-amber-700 font-bold">{entry.credit_account}</td>
                  <td className="p-3 text-right font-bold text-foreground">₹{entry.amount.toLocaleString("en-IN")}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 text-[10px] font-bold border border-border bg-bg rounded-base">
                      {entry.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 2: Virtual Accounts */}
      {activeTab === "accounts" && (
        <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light overflow-x-auto">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider">
              Allocated RazorpayX Virtual Accounts
            </h3>
            <button
              onClick={() => setShowAccountModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold border-2 border-border bg-main text-main-foreground rounded-base shadow-light"
            >
              <Plus className="size-4" /> Allocate Account
            </button>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {accounts.map((acc) => (
              <div key={acc.account_id} className="border-2 border-border p-4 rounded-base bg-main/5 flex flex-col justify-between gap-3">
                <div>
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="font-heading text-lg text-foreground">{acc.fork_city} Fork</span>
                    <span className="px-2 py-0.5 text-[10px] border border-border bg-green-500/20 text-green-700 rounded-base font-bold">
                      {acc.status}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground font-medium mt-0.5">{acc.department}</div>
                </div>

                <div className="border-t border-border pt-2 flex flex-col gap-1 font-mono text-xs">
                  <div className="text-muted-foreground text-[10px]">UPI Handle:</div>
                  <div className="font-bold text-foreground">{acc.upi_id}</div>
                  <div className="text-muted-foreground text-[10px] mt-1">Available Allocation:</div>
                  <div className="text-xl font-bold text-green-700">₹{acc.balance.toLocaleString("en-IN")}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Expenses */}
      {activeTab === "expenses" && (
        <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light overflow-x-auto">
          <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider mb-4">
            Expense Approval Queue
          </h3>

          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-border bg-main/10 font-heading text-foreground">
                <th className="p-3">Submitter / Dept</th>
                <th className="p-3">Category</th>
                <th className="p-3">Amount</th>
                <th className="p-3">Receipt</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Approval Action</th>
              </tr>
            </thead>
            <tbody>
              {expenses.map((exp) => (
                <tr key={exp.expense_id} className="border-b border-border/50 hover:bg-main/5">
                  <td className="p-3">
                    <div className="font-bold text-foreground">{exp.submitter_name}</div>
                    <div className="text-[10px] text-muted-foreground font-mono">{exp.department}</div>
                  </td>
                  <td className="p-3 font-semibold text-foreground">{exp.category}</td>
                  <td className="p-3 font-bold font-mono text-foreground">₹{exp.amount.toLocaleString("en-IN")}</td>
                  <td className="p-3">
                    {exp.receipt_url ? (
                      <a href={exp.receipt_url} target="_blank" rel="noreferrer" className="text-main underline font-bold">
                        View Receipt
                      </a>
                    ) : (
                      <span className="text-muted-foreground">No Receipt</span>
                    )}
                  </td>
                  <td className="p-3">
                    <span
                      className={`px-2.5 py-1 rounded-base font-bold text-[10px] border border-border ${
                        exp.status === "APPROVED"
                          ? "bg-green-500/20 text-green-700"
                          : exp.status === "REJECTED"
                          ? "bg-red-500/20 text-red-700"
                          : "bg-amber-500/20 text-amber-700"
                      }`}
                    >
                      {exp.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    {exp.status === "PENDING" ? (
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleReviewExpense(exp.expense_id, true)}
                          className="px-2.5 py-1 text-[10px] font-bold border-2 border-border bg-green-500 text-black rounded-base"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleReviewExpense(exp.expense_id, false)}
                          className="px-2.5 py-1 text-[10px] font-bold border-2 border-border bg-red-500 text-white rounded-base"
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span className="text-[10px] text-muted-foreground italic font-mono">
                        {exp.approver_note || "Processed"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Journal Modal */}
      {showJournalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="border-4 border-border bg-bg p-6 rounded-base shadow-light w-full max-w-md">
            <h3 className="text-lg font-heading font-bold text-foreground mb-4">Record Journal Entry</h3>
            <form onSubmit={handleCreateJournal} className="flex flex-col gap-3 text-xs">
              <div>
                <label className="font-bold block mb-1">Transaction Memo</label>
                <input
                  required
                  type="text"
                  value={journalForm.memo}
                  onChange={(e) => setJournalForm({ ...journalForm, memo: e.target.value })}
                  placeholder="e.g. Server Infrastructure Payment"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Debit Account Code</label>
                <input
                  required
                  type="text"
                  value={journalForm.debit_account}
                  onChange={(e) => setJournalForm({ ...journalForm, debit_account: e.target.value })}
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Credit Account Code</label>
                <input
                  required
                  type="text"
                  value={journalForm.credit_account}
                  onChange={(e) => setJournalForm({ ...journalForm, credit_account: e.target.value })}
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Amount (INR ₹)</label>
                <input
                  required
                  type="number"
                  min="1"
                  value={journalForm.amount}
                  onChange={(e) => setJournalForm({ ...journalForm, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => setShowJournalModal(false)}
                  className="px-4 py-2 border-2 border-border bg-bg font-bold rounded-base"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 border-2 border-border bg-main text-main-foreground font-bold rounded-base"
                >
                  Post Entry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Account Modal */}
      {showAccountModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="border-4 border-border bg-bg p-6 rounded-base shadow-light w-full max-w-md">
            <h3 className="text-lg font-heading font-bold text-foreground mb-4">Allocate Virtual Account</h3>
            <form onSubmit={handleCreateAccount} className="flex flex-col gap-3 text-xs">
              <div>
                <label className="font-bold block mb-1">Fork City</label>
                <input
                  required
                  type="text"
                  value={accountForm.fork_city}
                  onChange={(e) => setAccountForm({ ...accountForm, fork_city: e.target.value })}
                  placeholder="e.g. Gorakhpur"
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Department</label>
                <input
                  required
                  type="text"
                  value={accountForm.department}
                  onChange={(e) => setAccountForm({ ...accountForm, department: e.target.value })}
                  className="w-full border-2 border-border p-2 rounded-base bg-bg"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Initial Allocation (INR ₹)</label>
                <input
                  required
                  type="number"
                  min="0"
                  value={accountForm.initial_balance}
                  onChange={(e) => setAccountForm({ ...accountForm, initial_balance: parseFloat(e.target.value) || 0 })}
                  className="w-full border-2 border-border p-2 rounded-base bg-bg font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => setShowAccountModal(false)}
                  className="px-4 py-2 border-2 border-border bg-bg font-bold rounded-base"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 border-2 border-border bg-main text-main-foreground font-bold rounded-base"
                >
                  Allocate Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
