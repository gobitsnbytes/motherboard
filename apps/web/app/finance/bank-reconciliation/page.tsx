"use client";

import React, { useEffect, useRef, useState } from "react";
import { formatINR } from "../../../lib/finance-format";

interface BankLine {
  id: string;
  batch_label: string;
  statement_date: string;
  description: string;
  amount_paise: number;
  direction: string;
  status: string;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-3 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

const STATUS_COLOR: Record<string, string> = { unmatched: "#fc920d", matched: "#22c55e", ignored: "#6b6258" };

export default function BankReconciliationPage() {
  const [lines, setLines] = useState<BankLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("unmatched");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    setLoading(true);
    fetch(`/api/finance/bank-rec/lines?status=${statusFilter}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setLines(Array.isArray(d) ? d : []))
      .catch(() => setError("Unable to load bank statement lines."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/finance/bank-rec/import", { method: "POST", body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not import bank statement.");
    } else {
      const body = await res.json();
      alert(`Imported ${body.imported} lines (batch ${body.batch_label}).`);
    }
    load();
  };

  const ignoreLine = async (id: string) => {
    await fetch(`/api/finance/bank-rec/lines/${id}/ignore`, { method: "POST" });
    load();
  };

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Bank Reconciliation</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>
            Import a bank statement CSV (columns: date, description, amount_paise, direction) and match lines against the ledger.
          </p>
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])} />
          <button type="button" className={btnPrimary} onClick={() => fileRef.current?.click()}>
            Upload Statement CSV
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>}

      <div className="mb-5 flex flex-wrap gap-1 border-b-2 border-[#e4dcce] pb-0">
        {["unmatched", "matched", "ignored"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`mb-[-2px] min-h-11 cursor-pointer border-b-2 px-3 font-heading text-xs tracking-[0.04em] ${statusFilter === s ? "border-orange font-bold text-orange" : "border-transparent text-[#6b6258]"}`}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : lines.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-[#c9bfae] p-10 text-center font-base text-[#6b6258]">No {statusFilter} lines.</div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {lines.map((l) => (
            <div key={l.id} style={{ ...box, borderLeft: `4px solid ${STATUS_COLOR[l.status]}` }} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-base text-sm font-semibold text-[#120f0a]">{l.description}</div>
                  <div className="mt-1 font-heading text-[10px] uppercase tracking-[0.08em] text-[#6b6258]">
                    {l.statement_date} · {l.direction} · batch {l.batch_label}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <div className="font-heading text-base font-extrabold text-[#120f0a]">{formatINR(l.amount_paise)}</div>
                  {l.status === "unmatched" && (
                    <button type="button" className={btnSecondary} onClick={() => ignoreLine(l.id)}>
                      Ignore
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
