"use client";

import React, { useEffect, useState } from "react";
import { formatINR, currentFyLabel } from "../../../lib/finance-format";

interface Donor {
  id: string;
  name: string;
  donor_type: string;
  pan: string | null;
  is_foreign_source: boolean;
}

interface Donation {
  id: string;
  donor_id: string;
  receipt_number: string | null;
  donation_date: string;
  amount_paise: number;
  mode: string;
  status: string;
  claim_80g: boolean;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";
const btnSecondary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-[#120f0a] bg-white px-3 py-2 font-heading text-xs font-bold text-[#120f0a] shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

export default function DonationsPage() {
  const [donors, setDonors] = useState<Donor[]>([]);
  const [donations, setDonations] = useState<Donation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDonorForm, setShowDonorForm] = useState(false);
  const [showDonationForm, setShowDonationForm] = useState(false);

  const [donorForm, setDonorForm] = useState({ name: "", donor_type: "individual", pan: "", is_foreign_source: false });
  const [donationForm, setDonationForm] = useState({
    donor_id: "",
    donation_date: new Date().toISOString().slice(0, 10),
    amount: "",
    mode: "bank_transfer",
    purpose: "",
    claim_80g: true,
  });

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch("/api/finance/donors").then((r) => (r.ok ? r.json() : [])),
      fetch("/api/finance/donations").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([d, don]) => {
        setDonors(Array.isArray(d) ? d : []);
        setDonations(Array.isArray(don) ? don : []);
      })
      .catch(() => setError("Unable to load donations."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const createDonor = async () => {
    const res = await fetch("/api/finance/donors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(donorForm),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not create donor.");
    } else {
      setShowDonorForm(false);
      setDonorForm({ name: "", donor_type: "individual", pan: "", is_foreign_source: false });
      load();
    }
  };

  const createDonation = async () => {
    setError(null);
    const res = await fetch("/api/finance/donations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        donor_id: donationForm.donor_id,
        donation_date: donationForm.donation_date,
        amount_paise: Math.round(Number(donationForm.amount) * 100),
        mode: donationForm.mode,
        purpose: donationForm.purpose || null,
        claim_80g: donationForm.claim_80g,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not record donation.");
    } else {
      setShowDonationForm(false);
      setDonationForm({ ...donationForm, amount: "", purpose: "" });
      load();
    }
  };

  const confirmDonation = async (id: string) => {
    const res = await fetch(`/api/finance/donations/${id}/confirm`, { method: "POST" });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not confirm donation (maker-checker: a different user must confirm).");
    }
    load();
  };

  const donorName = (id: string) => donors.find((d) => d.id === id)?.name || "Unknown donor";

  return (
    <div className="font-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Donations &amp; Receipts</h1>
          <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>
            Cash receipts ≥ ₹2,00,000 are blocked (s.269ST). Foreign-source contributions are blocked without an FCRA registration on file.
            Receipt numbers are allocated on confirmation, by a different user than the one who recorded it.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={`/api/finance/reports/form10bd?fy=${currentFyLabel()}`} className={btnSecondary}>
            Download Form 10BD (CSV)
          </a>
          <button type="button" className={btnSecondary} onClick={() => setShowDonorForm((v) => !v)}>
            {showDonorForm ? "Cancel" : "+ New Donor"}
          </button>
          <button type="button" className={btnPrimary} onClick={() => setShowDonationForm((v) => !v)}>
            {showDonationForm ? "Cancel" : "+ Record Donation"}
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>}

      {showDonorForm && (
        <div style={box} className="mb-6 grid grid-cols-1 gap-3 p-5 sm:grid-cols-2">
          <input
            placeholder="Donor name"
            value={donorForm.name}
            onChange={(e) => setDonorForm({ ...donorForm, name: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
          />
          <select
            value={donorForm.donor_type}
            onChange={(e) => setDonorForm({ ...donorForm, donor_type: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
          >
            <option value="individual">Individual</option>
            <option value="huf">HUF</option>
            <option value="company">Company</option>
            <option value="trust">Trust</option>
            <option value="foreign">Foreign</option>
            <option value="other">Other</option>
          </select>
          <input
            placeholder="PAN (required to claim 80G)"
            value={donorForm.pan}
            onChange={(e) => setDonorForm({ ...donorForm, pan: e.target.value.toUpperCase() })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
          />
          <label className="flex min-h-11 items-center gap-2 font-base text-sm">
            <input
              type="checkbox"
              checked={donorForm.is_foreign_source}
              onChange={(e) => setDonorForm({ ...donorForm, is_foreign_source: e.target.checked })}
            />
            Foreign-source donor (FCRA applies)
          </label>
          <div className="sm:col-span-2">
            <button type="button" onClick={createDonor} disabled={!donorForm.name} className={btnPrimary}>
              Save Donor
            </button>
          </div>
        </div>
      )}

      {showDonationForm && (
        <div style={box} className="mb-6 grid grid-cols-1 gap-3 p-5 sm:grid-cols-2">
          <select
            value={donationForm.donor_id}
            onChange={(e) => setDonationForm({ ...donationForm, donor_id: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm sm:col-span-2"
          >
            <option value="">Select donor…</option>
            {donors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} {d.is_foreign_source ? "(foreign)" : ""}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={donationForm.donation_date}
            onChange={(e) => setDonationForm({ ...donationForm, donation_date: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
          />
          <input
            type="number"
            placeholder="Amount (₹)"
            value={donationForm.amount}
            onChange={(e) => setDonationForm({ ...donationForm, amount: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
          />
          <select
            value={donationForm.mode}
            onChange={(e) => setDonationForm({ ...donationForm, mode: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-2 font-base text-sm"
          >
            <option value="bank_transfer">Bank transfer</option>
            <option value="upi">UPI</option>
            <option value="cheque">Cheque</option>
            <option value="cash">Cash (limits apply)</option>
            <option value="card">Card</option>
            <option value="in_kind">In-kind</option>
          </select>
          <input
            placeholder="Purpose (optional)"
            value={donationForm.purpose}
            onChange={(e) => setDonationForm({ ...donationForm, purpose: e.target.value })}
            className="min-h-11 rounded-base border-2 border-[#120f0a] px-3 font-base text-sm"
          />
          <label className="flex min-h-11 items-center gap-2 font-base text-sm">
            <input
              type="checkbox"
              checked={donationForm.claim_80g}
              onChange={(e) => setDonationForm({ ...donationForm, claim_80g: e.target.checked })}
            />
            Issue 80G-eligible receipt (requires donor PAN)
          </label>
          <div className="sm:col-span-2">
            <button type="button" onClick={createDonation} disabled={!donationForm.donor_id || !donationForm.amount} className={btnPrimary}>
              Record Donation
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
      ) : donations.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-[#c9bfae] p-10 text-center font-base text-[#6b6258]">No donations recorded.</div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {donations.map((d) => (
            <div key={d.id} style={box} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-base text-sm font-semibold text-[#120f0a]">{donorName(d.donor_id)}</div>
                  <div className="mt-1 font-heading text-[10px] uppercase tracking-[0.08em] text-[#6b6258]">
                    {d.receipt_number || "no receipt yet"} · {d.donation_date} · {d.mode}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <div className="font-heading text-base font-extrabold text-[#120f0a]">{formatINR(d.amount_paise)}</div>
                  {d.status === "recorded" ? (
                    <button type="button" className={btnPrimary} onClick={() => confirmDonation(d.id)}>
                      Confirm
                    </button>
                  ) : (
                    <span className="font-heading text-[9px] font-bold uppercase text-emerald-600">{d.status}</span>
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
