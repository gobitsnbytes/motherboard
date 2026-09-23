"use client";

import React, { useEffect, useState } from "react";
import { formatINR, currentFyLabel } from "../../../lib/finance-format";

interface Vendor {
  id: string;
  name: string;
  pan: string | null;
  gstin: string | null;
  category: string | null;
}

interface Bill {
  id: string;
  vendor_id: string;
  bill_number: string;
  bill_date: string;
  amount_paise: number;
  tds_section: string | null;
  tds_amount_paise: number;
  status: string;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-3 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

const TDS_SECTIONS = ["194C", "194J", "194H", "194I", "194Q"];

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showVendorForm, setShowVendorForm] = useState(false);
  const [showBillForm, setShowBillForm] = useState(false);
  const [quarter, setQuarter] = useState(1);

  const [vendorForm, setVendorForm] = useState({ name: "", pan: "", gstin: "", category: "" });
  const [billForm, setBillForm] = useState({
    vendor_id: "",
    bill_number: "",
    bill_date: new Date().toISOString().slice(0, 10),
    amount: "",
    tds_section: "",
    tds_rate: "",
  });

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch("/api/finance/vendors").then((r) => (r.ok ? r.json() : [])),
      fetch("/api/finance/bills").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([v, b]) => {
        setVendors(Array.isArray(v) ? v : []);
        setBills(Array.isArray(b) ? b : []);
      })
      .catch(() => setError("Unable to load vendors."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const createVendor = async () => {
    const res = await fetch("/api/finance/vendors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(vendorForm),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not create vendor.");
    } else {
      setShowVendorForm(false);
      setVendorForm({ name: "", pan: "", gstin: "", category: "" });
      load();
    }
  };

  const createBill = async () => {
    const res = await fetch("/api/finance/bills", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vendor_id: billForm.vendor_id,
        bill_number: billForm.bill_number,
        bill_date: billForm.bill_date,
        amount_paise: Math.round(Number(billForm.amount) * 100),
        tds_section: billForm.tds_section || null,
        tds_rate_bps: billForm.tds_rate ? Math.round(Number(billForm.tds_rate) * 100) : null,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not create bill.");
    } else {
      setShowBillForm(false);
      setBillForm({ ...billForm, bill_number: "", amount: "" });
      load();
    }
  };

  const payBill = async (id: string) => {
    const res = await fetch(`/api/finance/bills/${id}/pay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payment_mode: "bank_transfer" }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not initiate payment.");
    } else {
      alert("Draft payment voucher created — submit and get a different user to approve it under Vouchers.");
    }
    load();
  };

  const vendorName = (id: string) => vendors.find((v) => v.id === id)?.name || "Unknown vendor";

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Vendors &amp; Bills</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>
            Bills book the accrual immediately (expense vs payable + TDS payable). Paying a bill creates a draft voucher — maker-checker applies.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))} className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-xs">
            <option value={1}>Q1 (Apr–Jun)</option>
            <option value={2}>Q2 (Jul–Sep)</option>
            <option value={3}>Q3 (Oct–Dec)</option>
            <option value={4}>Q4 (Jan–Mar)</option>
          </select>
          <a href={`/api/finance/reports/tds-quarterly?fy=${currentFyLabel()}&quarter=${quarter}`} className={btnSecondary}>
            Download TDS CSV (26Q-style)
          </a>
          <button type="button" className={btnSecondary} onClick={() => setShowVendorForm((v) => !v)}>
            {showVendorForm ? "Cancel" : "+ New Vendor"}
          </button>
          <button type="button" className={btnPrimary} onClick={() => setShowBillForm((v) => !v)}>
            {showBillForm ? "Cancel" : "+ New Bill"}
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>}

      {showVendorForm && (
        <div style={box} className="mb-6 grid grid-cols-1 gap-3 p-5 sm:grid-cols-2">
          <input placeholder="Vendor name" value={vendorForm.name} onChange={(e) => setVendorForm({ ...vendorForm, name: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input placeholder="Category (optional)" value={vendorForm.category} onChange={(e) => setVendorForm({ ...vendorForm, category: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input placeholder="PAN" value={vendorForm.pan} onChange={(e) => setVendorForm({ ...vendorForm, pan: e.target.value.toUpperCase() })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input placeholder="GSTIN (optional)" value={vendorForm.gstin} onChange={(e) => setVendorForm({ ...vendorForm, gstin: e.target.value.toUpperCase() })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <div className="sm:col-span-2">
            <button type="button" onClick={createVendor} disabled={!vendorForm.name} className={btnPrimary}>
              Save Vendor
            </button>
          </div>
        </div>
      )}

      {showBillForm && (
        <div style={box} className="mb-6 grid grid-cols-1 gap-3 p-5 sm:grid-cols-2">
          <select value={billForm.vendor_id} onChange={(e) => setBillForm({ ...billForm, vendor_id: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm sm:col-span-2">
            <option value="">Select vendor…</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <input placeholder="Bill number" value={billForm.bill_number} onChange={(e) => setBillForm({ ...billForm, bill_number: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input type="date" value={billForm.bill_date} onChange={(e) => setBillForm({ ...billForm, bill_date: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <input type="number" placeholder="Amount (₹)" value={billForm.amount} onChange={(e) => setBillForm({ ...billForm, amount: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          <select value={billForm.tds_section} onChange={(e) => setBillForm({ ...billForm, tds_section: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm">
            <option value="">No TDS</option>
            {TDS_SECTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {billForm.tds_section && (
            <input type="number" placeholder="TDS rate % (confirm with CA)" value={billForm.tds_rate} onChange={(e) => setBillForm({ ...billForm, tds_rate: e.target.value })} className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm" />
          )}
          <div className="sm:col-span-2">
            <button type="button" onClick={createBill} disabled={!billForm.vendor_id || !billForm.bill_number || !billForm.amount} className={btnPrimary}>
              Save Bill
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : bills.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-[#c9bfae] p-10 text-center font-base text-[#6b6258]">No bills yet.</div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {bills.map((b) => (
            <div key={b.id} style={box} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-base text-sm font-semibold text-[#120f0a]">
                    {vendorName(b.vendor_id)} — {b.bill_number}
                  </div>
                  <div className="mt-1 font-heading text-[10px] uppercase tracking-[0.08em] text-[#6b6258]">
                    {b.bill_date}
                    {b.tds_section && ` · TDS ${b.tds_section}: ${formatINR(b.tds_amount_paise)}`}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <div className="font-heading text-base font-extrabold text-[#120f0a]">{formatINR(b.amount_paise)}</div>
                  {b.status === "unpaid" ? (
                    <button type="button" className={btnPrimary} onClick={() => payBill(b.id)}>
                      Pay
                    </button>
                  ) : (
                    <span className="font-heading text-[9px] font-bold uppercase text-emerald-600">{b.status}</span>
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
