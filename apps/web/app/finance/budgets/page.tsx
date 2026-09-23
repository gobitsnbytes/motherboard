"use client";

import React, { useEffect, useState } from "react";
import { formatINR, currentFyLabel } from "../../../lib/finance-format";

interface Account {
  id: string;
  code: string;
  name: string;
}

interface Budget {
  id: string;
  fy_label: string;
  account_id: string;
  project_tag: string;
  budgeted_paise: number;
}

interface VsActual {
  account_id: string;
  project_tag: string;
  budgeted_paise: number;
  actual_paise: number;
  variance_paise: number;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-3 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

export default function BudgetsPage() {
  const fy = currentFyLabel();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [actuals, setActuals] = useState<VsActual[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ account_id: "", project_tag: "", amount: "", notes: "" });

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch("/api/finance/ledger/accounts").then((r) => (r.ok ? r.json() : [])),
      fetch(`/api/finance/budgets?fy=${fy}`).then((r) => (r.ok ? r.json() : [])),
      fetch(`/api/finance/budgets/vs-actuals?fy=${fy}`).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([a, b, v]) => {
        setAccounts(Array.isArray(a) ? a : []);
        setBudgets(Array.isArray(b) ? b : []);
        setActuals(Array.isArray(v) ? v : []);
      })
      .catch(() => setError("Unable to load budgets."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createBudget = async () => {
    const res = await fetch("/api/finance/budgets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fy_label: fy,
        account_id: form.account_id,
        project_tag: form.project_tag,
        budgeted_paise: Math.round(Number(form.amount) * 100),
        notes: form.notes || null,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not save budget.");
    } else {
      setShowForm(false);
      setForm({ account_id: "", project_tag: "", amount: "", notes: "" });
      load();
    }
  };

  const accountLabel = (id: string) => {
    const a = accounts.find((acc) => acc.id === id);
    return a ? `${a.code} — ${a.name}` : id;
  };

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Budgets</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>Per account/project, FY {fy}. Actuals are pulled live from the journal.</p>
        </div>
        <button type="button" className={btnPrimary} onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ New Budget Line"}
        </button>
      </div>

      {error && <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>}

      {showForm && (
        <div style={box} className="mb-6 grid grid-cols-1 gap-3 p-5 sm:grid-cols-2">
          <select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm sm:col-span-2">
            <option value="">Select account…</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
          <input placeholder="Project/city tag (optional, e.g. delhi)" value={form.project_tag} onChange={(e) => setForm({ ...form, project_tag: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input type="number" placeholder="Budgeted amount (₹)" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input placeholder="Notes (optional)" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm sm:col-span-2" />
          <div className="sm:col-span-2">
            <button type="button" onClick={createBudget} disabled={!form.account_id || !form.amount} className={btnPrimary}>
              Save Budget
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : budgets.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-[#c9bfae] p-10 text-center font-base text-[#6b6258]">No budgets set for FY {fy}.</div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {budgets.map((b) => {
            const actual = actuals.find((a) => a.account_id === b.account_id && a.project_tag === b.project_tag);
            const overBudget = actual && actual.variance_paise < 0;
            return (
              <div key={b.id} style={box} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-base text-sm font-semibold text-[#120f0a]">{accountLabel(b.account_id)}</div>
                    {b.project_tag && <div className="mt-0.5 font-heading text-[10px] uppercase tracking-[0.08em] text-[#6b6258]">{b.project_tag}</div>}
                  </div>
                  <div className="text-right">
                    <div className="font-base text-[11px] text-[#6b6258]">Budget: {formatINR(b.budgeted_paise)}</div>
                    {actual && (
                      <>
                        <div className="font-base text-[11px] text-[#6b6258]">Actual: {formatINR(actual.actual_paise)}</div>
                        <div className={`font-heading text-xs font-bold ${overBudget ? "text-red-600" : "text-emerald-600"}`}>
                          {overBudget ? "Over" : "Under"} by {formatINR(Math.abs(actual.variance_paise))}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
