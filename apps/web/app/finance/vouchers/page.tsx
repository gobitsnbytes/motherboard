"use client";

import React, { useEffect, useState } from "react";
import { formatINR } from "../../../lib/finance-format";

interface Account {
  id: string;
  code: string;
  name: string;
}

interface Voucher {
  id: string;
  voucher_type: string;
  voucher_number: string | null;
  fy_label: string;
  voucher_date: string;
  narration: string;
  amount_paise: number;
  payment_mode: string;
  status: string;
  created_by: string;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-3 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const STATUS_COLOR: Record<string, string> = {
  draft: "#6b6258",
  pending_approval: "#fc920d",
  posted: "#22c55e",
  rejected: "#ef4444",
  void: "#6b6258",
};

const TABS = ["all", "draft", "pending_approval", "posted", "rejected"] as const;

export default function VouchersPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("all");
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    voucher_type: "payment" as "payment" | "receipt" | "journal",
    voucher_date: new Date().toISOString().slice(0, 10),
    narration: "",
    amount: "",
    debit_account_id: "",
    credit_account_id: "",
    payment_mode: "bank_transfer",
  });

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch("/api/finance/ledger/accounts").then((r) => (r.ok ? r.json() : [])),
      fetch(`/api/finance/vouchers${tab === "all" ? "" : `?status=${tab}`}`).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([a, v]) => {
        setAccounts(Array.isArray(a) ? a : []);
        setVouchers(Array.isArray(v) ? v : []);
      })
      .catch(() => setError("Unable to load vouchers."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const createVoucher = async () => {
    setSubmitting(true);
    setError(null);
    const res = await fetch("/api/finance/vouchers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        voucher_type: form.voucher_type,
        voucher_date: form.voucher_date,
        narration: form.narration,
        amount_paise: Math.round(Number(form.amount) * 100),
        debit_account_id: form.debit_account_id || null,
        credit_account_id: form.credit_account_id || null,
        payment_mode: form.payment_mode,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not create voucher.");
    } else {
      setShowForm(false);
      setForm({ ...form, narration: "", amount: "", debit_account_id: "", credit_account_id: "" });
      load();
    }
    setSubmitting(false);
  };

  const act = async (id: string, action: "submit" | "approve" | "reject") => {
    const res = await fetch(`/api/finance/vouchers/${id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: action === "submit" ? undefined : JSON.stringify({ note: null }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || `Could not ${action} voucher.`);
    }
    load();
  };

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Vouchers</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>
            Payment, receipt &amp; journal vouchers. Numbers are allocated only on approval — maker-checker enforced (the creator cannot approve their own voucher).
          </p>
        </div>
        <button type="button" className={btnPrimary} onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ New Voucher"}
        </button>
      </div>

      {error && <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>}

      {showForm && (
        <div style={box} className="mb-6 p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Type</label>
              <select
                value={form.voucher_type}
                onChange={(e) => setForm({ ...form, voucher_type: e.target.value as any })}
                className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
              >
                <option value="payment">Payment</option>
                <option value="receipt">Receipt</option>
                <option value="journal">Journal</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Date</label>
              <input
                type="date"
                value={form.voucher_date}
                onChange={(e) => setForm({ ...form, voucher_date: e.target.value })}
                className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Narration</label>
              <input
                value={form.narration}
                onChange={(e) => setForm({ ...form, narration: e.target.value })}
                className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
                placeholder="Purpose of this voucher"
              />
            </div>
            <div>
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Amount (₹)</label>
              <input
                type="number"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Payment mode</label>
              <select
                value={form.payment_mode}
                onChange={(e) => setForm({ ...form, payment_mode: e.target.value })}
                className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
              >
                <option value="bank_transfer">Bank transfer</option>
                <option value="upi">UPI</option>
                <option value="cheque">Cheque</option>
                <option value="cash">Cash (limits apply)</option>
                <option value="card">Card</option>
              </select>
            </div>
            {form.voucher_type !== "receipt" && (
              <div>
                <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">
                  Debit account {form.voucher_type === "payment" ? "(expense/payable)" : ""}
                </label>
                <select
                  value={form.debit_account_id}
                  onChange={(e) => setForm({ ...form, debit_account_id: e.target.value })}
                  className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
                >
                  <option value="">Select…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {form.voucher_type !== "payment" && (
              <div>
                <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">
                  Credit account {form.voucher_type === "receipt" ? "(income/receivable)" : ""}
                </label>
                <select
                  value={form.credit_account_id}
                  onChange={(e) => setForm({ ...form, credit_account_id: e.target.value })}
                  className="min-h-11 w-full rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
                >
                  <option value="">Select…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div className="mt-4">
            <button type="button" onClick={createVoucher} disabled={submitting || !form.narration || !form.amount} className={btnPrimary}>
              {submitting ? "Saving…" : "Save Draft"}
            </button>
          </div>
        </div>
      )}

      <div className="mb-5 flex flex-wrap gap-1 border-b-2 border-[#e4dcce] pb-0">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`mb-[-2px] min-h-11 cursor-pointer border-b-2 px-3 font-heading text-xs tracking-[0.04em] ${tab === t ? "border-orange font-bold text-orange" : "border-transparent text-[#6b6258]"}`}
          >
            {t.replace("_", " ")}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : vouchers.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-[#c9bfae] p-10 text-center font-base text-[#6b6258]">No vouchers.</div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {vouchers.map((v) => {
            const color = STATUS_COLOR[v.status] ?? "#6b6258";
            return (
              <div key={v.id} style={{ ...box, borderLeft: `4px solid ${color}` }} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-base text-sm font-semibold text-[#120f0a]">{v.narration}</div>
                    <div className="mt-1 font-heading text-[10px] uppercase tracking-[0.08em] text-[#6b6258]">
                      {v.voucher_number || "unnumbered"} · {v.voucher_type} · {v.voucher_date} · {v.payment_mode}
                    </div>
                  </div>
                  <div className="ml-2 flex shrink-0 flex-col items-end gap-2">
                    <div className="font-heading text-base font-extrabold text-[#120f0a]">{formatINR(v.amount_paise)}</div>
                    <span className="font-heading text-[9px] font-bold uppercase" style={{ color }}>
                      {v.status.replace("_", " ")}
                    </span>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {v.status === "draft" && (
                    <button type="button" className={btnSecondary} onClick={() => act(v.id, "submit")}>
                      Submit for approval
                    </button>
                  )}
                  {v.status === "pending_approval" && (
                    <>
                      <button type="button" className={btnPrimary} onClick={() => act(v.id, "approve")}>
                        Approve
                      </button>
                      <button type="button" className={btnSecondary} onClick={() => act(v.id, "reject")}>
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
