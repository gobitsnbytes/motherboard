"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API = "";

interface Account { id: string; name: string; account_number: string; is_active: boolean; }

const inputClass =
  "box-border w-full rounded-base border-2 border-border bg-background px-3.5 py-2.5 font-base text-[13px] text-white outline-none focus:border-orange";

const labelClass =
  "mb-1.5 block font-heading text-[10px] uppercase tracking-[0.12em] text-muted-foreground";

export default function NewRequestPage() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [form, setForm] = useState({ from_account_id: "", to_account_id: "", amount: "", description: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getHeaders = (): Record<string, string> => ({ "Content-Type": "application/json" });

  useEffect(() => {
    fetch(`${API}/api/finance/accounts`, { headers: getHeaders() })
      .then(r => r.json())
      .then(d => setAccounts(Array.isArray(d) ? d : []));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const amountPaise = Math.round(parseFloat(form.amount) * 100);
    if (isNaN(amountPaise) || amountPaise <= 0) { setError("Enter a valid amount."); setSubmitting(false); return; }
    try {
      const res = await fetch(`${API}/api/finance/requests`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          from_account_id: form.from_account_id || null,
          to_account_id: form.to_account_id,
          amount_paise: amountPaise,
          description: form.description,
        }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail ?? "Failed"); }
      router.push("/finance/requests");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ fontFamily: "Inter, sans-serif", maxWidth: "520px" }}>
      <div style={{ marginBottom: "28px" }}>
        <Link href="/finance/requests" style={{ fontSize: "11px", color: "#555", textDecoration: "none", letterSpacing: "0.08em" }}>← Requests</Link>
        <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: "8px 0 4px" }}>New Money Request</h1>
        <p style={{ fontSize: "12px", color: "#6b6258" }}>Submit a virtual fund request for admin approval</p>
      </div>

      <div className="rounded-base border-2 border-border bg-main p-7 shadow-shadow" style={{ boxShadow: "4px 4px 0 0 #fc920d" }}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-[18px]">
          {/* Source */}
          <div>
            <label className={labelClass}>Source</label>
            <select value={form.from_account_id} onChange={e => setForm(f => ({ ...f, from_account_id: e.target.value }))} className={inputClass}>
              <option value="">Main Pool (Treasury)</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name} — {a.account_number}</option>
              ))}
            </select>
            <div className="mt-1 font-heading text-[10px] text-muted-foreground/60">Leave blank to draw from the main treasury pool</div>
          </div>

          {/* Destination */}
          <div>
            <label className={labelClass}>Destination Account *</label>
            <select required value={form.to_account_id} onChange={e => setForm(f => ({ ...f, to_account_id: e.target.value }))} className={inputClass}>
              <option value="">Select destination…</option>
              {accounts.filter(a => a.id !== form.from_account_id).map(a => (
                <option key={a.id} value={a.id}>{a.name} — {a.account_number}</option>
              ))}
            </select>
          </div>

          {/* Amount */}
          <div>
            <label className={labelClass}>Amount (₹) *</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 font-heading text-sm font-bold text-muted-foreground">₹</span>
              <input required type="number" min="0.01" step="0.01" placeholder="0.00" value={form.amount}
                onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                className={`${inputClass} pl-7`} />
            </div>
            <div className="mt-1 font-heading text-[10px] text-muted-foreground/60">Virtual rupees only — no real money is transferred</div>
          </div>

          {/* Description */}
          <div>
            <label className={labelClass}>Description / Purpose *</label>
            <textarea required rows={3} placeholder="Explain the purpose of this request…" value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className={`${inputClass} resize-vertical`} />
          </div>

          {error && (
            <div className="rounded-base border-2 border-burgundy bg-burgundy/10 px-3.5 py-2.5 font-base text-xs text-red-300">
              {error}
            </div>
          )}

          {/* Preview */}
          {form.amount && !isNaN(parseFloat(form.amount)) && (
            <div className="rounded-base border-2 border-orange/20 bg-orange/5 px-3.5 py-3">
              <div className="mb-1 font-heading text-[11px] text-muted-foreground">Request preview</div>
              <div className="font-heading text-lg font-extrabold text-orange">
                ₹{parseFloat(form.amount || "0").toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <div className="mt-0.5 font-heading text-[11px] text-muted-foreground">
                {form.from_account_id ? "Account Transfer" : "Pool Draw"} → pending admin approval
              </div>
            </div>
          )}

          <div className="flex gap-2.5">
            <button type="submit" disabled={submitting}
              className={`flex-1 rounded-base border-2 border-orange bg-orange py-2.5 font-heading text-[13px] font-bold text-black shadow-shadow ${submitting ? "cursor-not-allowed opacity-60" : "cursor-pointer transition-transform hover:translate-x-[3px] hover:translate-y-[3px] hover:shadow-none"}`}>
              {submitting ? "Submitting…" : "Submit Request"}
            </button>
            <Link href="/finance/requests"
              className="flex flex-1 items-center justify-center rounded-base border-2 border-border bg-transparent py-2.5 font-heading text-[13px] font-semibold text-muted-foreground no-underline">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
