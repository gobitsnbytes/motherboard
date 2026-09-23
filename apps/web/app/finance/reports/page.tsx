"use client";

import React, { useEffect, useState } from "react";
import { formatINR, currentFyLabel } from "../../../lib/finance-format";

interface Account {
  id: string;
  code: string;
  name: string;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-3 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

export default function ReportsPage() {
  const [fy, setFy] = useState(currentFyLabel());
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [glAccount, setGlAccount] = useState("");
  const [trialBalance, setTrialBalance] = useState<any[]>([]);
  const [incomeExp, setIncomeExp] = useState<any | null>(null);
  const [balanceSheet, setBalanceSheet] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/finance/ledger/accounts")
      .then((r) => (r.ok ? r.json() : []))
      .then((a) => setAccounts(Array.isArray(a) ? a : []));
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`/api/finance/reports/trial-balance?fy=${fy}`).then((r) => (r.ok ? r.json() : [])),
      fetch(`/api/finance/reports/income-expenditure?fy=${fy}`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/api/finance/reports/balance-sheet?as_of_fy=${fy}`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([tb, ie, bs]) => {
        setTrialBalance(Array.isArray(tb) ? tb : []);
        setIncomeExp(ie);
        setBalanceSheet(bs);
      })
      .finally(() => setLoading(false));
  }, [fy]);

  const totalDebit = trialBalance.reduce((s, r) => s + r.debit_total_paise, 0);
  const totalCredit = trialBalance.reduce((s, r) => s + r.credit_total_paise, 0);

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Reports</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>Every figure below is derived directly from the journal.</p>
        </div>
        <input
          value={fy}
          onChange={(e) => setFy(e.target.value)}
          placeholder="2026-27"
          className="min-h-11 w-28 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
        />
      </div>

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Trial balance */}
          <div style={box} className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-sm font-extrabold uppercase text-[#120f0a]">Trial Balance</h2>
              <a href={`/api/finance/reports/trial-balance?fy=${fy}&csv=true`} className={btnSecondary}>
                CSV
              </a>
            </div>
            <div className="max-h-72 overflow-y-auto">
              <table className="w-full font-base text-xs">
                <tbody>
                  {trialBalance.map((r) => (
                    <tr key={r.account_id} className="border-b border-[#eee]">
                      <td className="py-1 pr-2">
                        {r.code} {r.name}
                      </td>
                      <td className="py-1 text-right">{formatINR(r.balance_paise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 border-t-2 border-[#120f0a] pt-2 font-heading text-xs font-bold">
              Debits {formatINR(totalDebit)} = Credits {formatINR(totalCredit)}{" "}
              <span className={totalDebit === totalCredit ? "text-emerald-600" : "text-red-600"}>{totalDebit === totalCredit ? "✓ balanced" : "✗ out of balance"}</span>
            </div>
          </div>

          {/* Income & Expenditure */}
          <div style={box} className="p-5">
            <h2 className="mb-3 font-heading text-sm font-extrabold uppercase text-[#120f0a]">Income &amp; Expenditure</h2>
            {incomeExp && (
              <div className="font-base text-xs">
                <div className="mb-1 flex justify-between">
                  <span>Total Income</span>
                  <span className="font-bold">{formatINR(incomeExp.total_income_paise)}</span>
                </div>
                <div className="mb-1 flex justify-between">
                  <span>Total Expenditure</span>
                  <span className="font-bold">{formatINR(incomeExp.total_expense_paise)}</span>
                </div>
                <div className="flex justify-between border-t-2 border-[#120f0a] pt-2 font-heading font-bold">
                  <span>Surplus / (Deficit)</span>
                  <span>{formatINR(incomeExp.surplus_deficit_paise)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Balance Sheet */}
          <div style={box} className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-sm font-extrabold uppercase text-[#120f0a]">Balance Sheet</h2>
            </div>
            {balanceSheet && (
              <div className="font-base text-xs">
                <div className="mb-1 flex justify-between">
                  <span>Total Assets</span>
                  <span className="font-bold">{formatINR(balanceSheet.total_assets_paise)}</span>
                </div>
                <div className="mb-1 flex justify-between">
                  <span>Total Liabilities</span>
                  <span className="font-bold">{formatINR(balanceSheet.total_liabilities_paise)}</span>
                </div>
                <div className="mb-1 flex justify-between">
                  <span>Total Funds / Equity</span>
                  <span className="font-bold">{formatINR(balanceSheet.total_equity_paise)}</span>
                </div>
                <div className={`mt-2 border-t-2 border-[#120f0a] pt-2 font-heading font-bold ${balanceSheet.balanced ? "text-emerald-600" : "text-red-600"}`}>
                  {balanceSheet.balanced ? "✓ Assets = Liabilities + Funds" : "✗ Out of balance"}
                </div>
              </div>
            )}
          </div>

          {/* Receipts & payments / donors / general ledger downloads */}
          <div style={box} className="p-5">
            <h2 className="mb-3 font-heading text-sm font-extrabold uppercase text-[#120f0a]">More Reports</h2>
            <div className="flex flex-col gap-2">
              <a href={`/api/finance/reports/receipts-payments?fy=${fy}&csv=true`} className={btnSecondary}>
                Receipts &amp; Payments (CSV)
              </a>
              <a href={`/api/finance/reports/donors?fy=${fy}&csv=true`} className={btnSecondary}>
                Donor Report (CSV)
              </a>
              <div className="flex flex-wrap items-center gap-2">
                <select value={glAccount} onChange={(e) => setGlAccount(e.target.value)} className="min-h-11 flex-1 rounded-base border-2 border-[#120f0a] px-2 font-base text-xs">
                  <option value="">General ledger — select account…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </select>
                {glAccount && (
                  <a href={`/api/finance/reports/general-ledger/${glAccount}?fy=${fy}&csv=true`} className={btnSecondary}>
                    CSV
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
