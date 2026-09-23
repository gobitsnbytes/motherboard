"use client";

import React, { useEffect, useState } from "react";

interface OrgSettings {
  pan: string | null;
  tan: string | null;
  gstin: string | null;
  income_tax_80g_reg_no: string | null;
  income_tax_80g_valid_upto: string | null;
  income_tax_12a_reg_no: string | null;
  fcra_registration_no: string | null;
  fcra_valid_upto: string | null;
}

interface RazorpayXStatus {
  configured: boolean;
  webhook_configured: boolean;
}

const box: React.CSSProperties = { border: "2px solid #120f0a", borderRadius: "4px", background: "#fff", boxShadow: "4px 4px 0 0 #120f0a" };
const btnPrimary =
  "inline-flex min-h-11 items-center justify-center rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-[3px_3px_0_0_#120f0a] transition-transform hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50";

const FIELDS: { key: keyof OrgSettings; label: string; hint: string; type?: string }[] = [
  { key: "pan", label: "PAN", hint: "Foundation's Permanent Account Number" },
  { key: "tan", label: "TAN", hint: "Required to deposit and report TDS" },
  { key: "gstin", label: "GSTIN", hint: "If GST-registered" },
  { key: "income_tax_12a_reg_no", label: "12A Registration No.", hint: "Income-tax exemption registration" },
  { key: "income_tax_80g_reg_no", label: "80G Registration No.", hint: "Enables donor tax-deduction receipts" },
  { key: "income_tax_80g_valid_upto", label: "80G Valid Upto", hint: "", type: "date" },
  { key: "fcra_registration_no", label: "FCRA Registration No.", hint: "Required before accepting any foreign-source contribution" },
  { key: "fcra_valid_upto", label: "FCRA Valid Upto", hint: "", type: "date" },
];

export default function FinanceSettingsPage() {
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [razorpayx, setRazorpayx] = useState<RazorpayXStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = () => {
    Promise.all([
      fetch("/api/finance/settings/org").then((r) => (r.ok ? r.json() : null)),
      fetch("/api/finance/razorpayx/status").then((r) => (r.ok ? r.json() : null)),
    ]).then(([s, rx]) => {
      setSettings(s);
      setRazorpayx(rx);
    });
  };

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    const res = await fetch("/api/finance/settings/org", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Could not save settings.");
    } else {
      setSaved(true);
      load();
    }
    setSaving(false);
  };

  return (
    <div className="font-heading">
      <div className="mb-6">
        <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#120f0a", margin: 0 }}>Finance Settings</h1>
        <p style={{ fontSize: "12px", color: "#6b6258", marginTop: "4px" }}>
          Legal registration numbers. Nothing here is invented — leave a field blank until the Foundation actually holds that registration; blank fields
          keep the related guard (e.g. FCRA) blocking by default.
        </p>
      </div>

      {error && <div className="mb-4 rounded-base border-2 border-red-700 bg-red-50 p-3 font-base text-xs font-bold text-red-900">{error}</div>}
      {saved && <div className="mb-4 rounded-base border-2 border-emerald-700 bg-emerald-50 p-3 font-base text-xs font-bold text-emerald-900">Saved.</div>}

      <div style={box} className="mb-6 p-5">
        <h2 className="mb-4 font-heading text-sm font-extrabold uppercase text-[#120f0a]">Legal &amp; Tax Registrations</h2>
        {settings ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <div key={f.key}>
                <label className="mb-1 block font-heading text-[10px] uppercase tracking-[0.1em] text-[#6b6258]">{f.label}</label>
                <input
                  type={f.type || "text"}
                  value={(settings[f.key] as string) || ""}
                  onChange={(e) => setSettings({ ...settings, [f.key]: e.target.value || null })}
                  placeholder="Not on file"
                  className="box-border w-full rounded-base border-2 border-[#120f0a] px-3 py-2 font-base text-sm"
                />
                {f.hint && <p className="mt-1 font-base text-[10px] text-[#6b6258]">{f.hint}</p>}
              </div>
            ))}
          </div>
        ) : (
          <div className="font-base text-[13px] text-[#6b6258]">Loading…</div>
        )}
        <div className="mt-5">
          <button type="button" className={btnPrimary} onClick={save} disabled={saving || !settings}>
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </div>

      <div style={box} className="p-5">
        <h2 className="mb-3 font-heading text-sm font-extrabold uppercase text-[#120f0a]">RazorpayX Payouts</h2>
        {razorpayx?.configured ? (
          <div className="rounded-base border-2 border-emerald-700 bg-emerald-50 p-3 font-base text-xs font-bold text-emerald-900">Connected</div>
        ) : (
          <div className="rounded-base border-2 border-[#c9bfae] bg-[#f8f1e7] p-3 font-base text-xs text-[#6b6258]">
            <div className="mb-1 font-heading text-xs font-bold uppercase text-[#120f0a]">Not connected</div>
            This is a placeholder integration seam — no live payouts run through it yet. Set <code>RAZORPAYX_KEY_ID</code>,{" "}
            <code>RAZORPAYX_SECRET</code>, and <code>RAZORPAYX_WEBHOOK_SECRET</code> on the API to configure it once the real RazorpayX Payouts API is
            wired in.
          </div>
        )}
      </div>
    </div>
  );
}
