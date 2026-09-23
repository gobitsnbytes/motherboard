"use client";

import React, { useEffect, useState } from "react";
import { formatINR, currentFyLabel } from "../../../lib/finance-format";

interface Account {
  id: string;
  code: string;
  name: string;
  account_type: string;
  normal_balance: string;
  fund_type: string;
}

interface JournalLine {
  account_code: string;
  account_name: string;
  debit_paise: number;
  credit_paise: number;
  description: string | null;
}

interface JournalEntry {
  id: string;
  fy_label: string;
  entry_date: string;
  memo: string;
  source_type: string;
  is_reversed: boolean;
  reverses_entry_id: string | null;
  lines: JournalLine[];
}

interface Period {
  fy_label: string;
  start_date: string;
  end_date: string;
  is_closed: boolean;
}

const box: React.CSSProperties = {
  border: "2px solid #120f0a",
  borderRadius: "4px",
  background: "#fff",
  boxShadow: "4px 4px 0 0 #120f0a",
};

const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-4 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

export default function LedgerPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState([
    { account_id: "", side: "debit" as "debit" | "credit", amount: "" },
    { account_id: "", side: "credit" as "debit" | "credit", amount: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetch("/api/finance/ledger/accounts").then((r) => (r.ok ? r.json() : [])),
      fetch("/api/finance/ledger/entries?limit=50").then((r) => (r.ok ? r.json() : [])),
      fetch("/api/finance/periods").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([a, e, p]) => {
        setAccounts(Array.isArray(a) ? a : []);
        setEntries(Array.isArray(e) ? e : []);
        setPeriods(Array.isArray(p) ? p : []);
      })
      .catch(() => setError("Unable to load the ledger."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const addLine = () => setLines((prev) => [...prev, { account_id: "", side: "debit", amount: "" }]);
  const removeLine = (i: number) => setLines((prev) => prev.filter((_, idx) => idx !== i));

  const submitEntry = async () => {
    setSubmitting(true);
    const payload = {
      entry_date: entryDate,
      memo,
      lines: lines
        .filter((l) => l.account_id && l.amount)
        .map((l) => ({
          account_id: l.account_id,
          debit_paise: l.side === "debit" ? Math.round(Number(l.amount) * 100) : 0,
          credit_paise: l.side === "credit" ? Math.round(Number(l.amount) * 100) : 0,
        })),
    };
    const res = await fetch("/api/finance/ledger/entries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not post journal entry.");
    } else {
      setMemo("");
      setLines([
        { account_id: "", side: "debit", amount: "" },
        { account_id: "", side: "credit", amount: "" },
      ]);
      setShowForm(false);
      load();
    }
    setSubmitting(false);
  };

  const reverseEntry = async (id: string) => {
    if (!confirm("Post a reversal entry for this posting? The original stays on the books, untouched.")) return;
    const res = await fetch(`/api/finance/ledger/entries/${id}/reverse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ memo: null }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not reverse entry.");
    }
    load();
  };

  const togglePeriod = async (fy: string, close: boolean) => {
    const res = await fetch(`/api/finance/periods/${fy}/${close ? "close" : "reopen"}`, { method: "POST" });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not update period.");
    }
    load();
  };

  const fy = currentFyLabel();
  const currentPeriod = periods.find((p) => p.fy_label === fy);

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>General Ledger</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>
            Append-only double-entry journal. Corrections post a reversal — nothing here is ever edited or deleted.
          </p>
        </div>
        <button type="button" className={btnPrimary} onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ Post Journal Entry"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>
      )}

      {/* Fiscal period status */}
      <div style={box} className="mb-5 flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="font-heading text-xs font-bold uppercase tracking-wide text-[#120f0a]">
            Financial Year {fy} {currentPeriod?.is_closed ? "— Closed" : "— Open"}
          </div>
          <div className="mt-1 font-base text-[11px] text-[#6b6258]">1 April – 31 March. A closed period blocks all new postings.</div>
        </div>
        <button
          type="button"
          className={btnSecondary}
          onClick={() => togglePeriod(fy, !currentPeriod?.is_closed)}
        >
          {currentPeriod?.is_closed ? "Reopen Period" : "Close Period"}
        </button>
      </div>

      {showForm && (
        <div style={box} className="mb-6 p-5">
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Date</label>
              <input
                type="date"
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
                className="box-border w-full rounded-base border-2 border-[#120f0a] px-3 py-2 font-base text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">Memo</label>
              <input
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="What is this posting for?"
                className="box-border w-full rounded-base border-2 border-[#120f0a] px-3 py-2 font-base text-sm"
              />
            </div>
          </div>

          <div className="space-y-2">
            {lines.map((line, i) => (
              <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_100px_120px_44px]">
                <select
                  value={line.account_id}
                  onChange={(e) =>
                    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, account_id: e.target.value } : l)))
                  }
                  className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
                >
                  <option value="">Select account…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </select>
                <select
                  value={line.side}
                  onChange={(e) =>
                    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, side: e.target.value as "debit" | "credit" } : l)))
                  }
                  className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
                >
                  <option value="debit">Debit</option>
                  <option value="credit">Credit</option>
                </select>
                <input
                  type="number"
                  placeholder="₹ amount"
                  value={line.amount}
                  onChange={(e) => setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, amount: e.target.value } : l)))}
                  className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
                />
                <button
                  type="button"
                  onClick={() => removeLine(i)}
                  disabled={lines.length <= 2}
                  className="min-h-11 rounded-base border-2 border-[#120f0a] font-heading text-xs font-bold disabled:opacity-30"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={addLine} className={btnSecondary}>
              + Add Line
            </button>
            <button type="button" onClick={submitEntry} disabled={submitting || !memo} className={btnPrimary}>
              {submitting ? "Posting…" : "Post Entry"}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-[#c9bfae] p-10 text-center font-base text-[#6b6258]">No journal entries yet.</div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {entries.map((e) => (
            <div key={e.id} style={box} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-base text-sm font-semibold text-[#120f0a]">{e.memo}</div>
                  <div className="mt-1 font-heading text-[10px] uppercase tracking-[0.08em] text-[#6b6258]">
                    {e.entry_date} · {e.source_type} · FY {e.fy_label}
                    {e.is_reversed && <span className="ml-2 text-red-700">reversed</span>}
                  </div>
                </div>
                {!e.is_reversed && e.source_type !== "reversal" && (
                  <button type="button" onClick={() => reverseEntry(e.id)} className={btnSecondary}>
                    Reverse
                  </button>
                )}
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[420px] font-base text-xs">
                  <thead>
                    <tr className="border-b border-[#c9bfae] text-left text-[10px] uppercase tracking-wide text-[#6b6258]">
                      <th className="py-1 pr-2">Account</th>
                      <th className="py-1 pr-2 text-right">Debit</th>
                      <th className="py-1 text-right">Credit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {e.lines.map((l, i) => (
                      <tr key={i} className="border-b border-[#eee]">
                        <td className="py-1 pr-2">
                          {l.account_code} — {l.account_name}
                        </td>
                        <td className="py-1 pr-2 text-right">{l.debit_paise ? formatINR(l.debit_paise) : ""}</td>
                        <td className="py-1 text-right">{l.credit_paise ? formatINR(l.credit_paise) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
