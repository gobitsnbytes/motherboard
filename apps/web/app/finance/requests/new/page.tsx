"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API = "";

interface Account { id: string; name: string; account_number: string; is_active: boolean; }

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
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", background: "#0d0d0d", border: "2px solid #2a2a2a", borderRadius: "3px",
    padding: "10px 14px", color: "#fff", fontFamily: "Inter, sans-serif", fontSize: "13px",
    outline: "none", boxSizing: "border-box",
  };

  const selStyle: React.CSSProperties = { ...inputStyle };

  return (
    <div style={{ fontFamily: "Inter, sans-serif", maxWidth: "520px" }}>
      <div style={{ marginBottom: "28px" }}>
        <Link href="/finance/requests" style={{ fontSize: "11px", color: "#555", textDecoration: "none", letterSpacing: "0.08em" }}>← Requests</Link>
        <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#fff", margin: "8px 0 4px" }}>New Money Request</h1>
        <p style={{ fontSize: "12px", color: "#555" }}>Submit a virtual fund request for admin approval</p>
      </div>

      <div style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "28px", boxShadow: "4px 4px 0 0 #fc920d" }}>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          {/* Source */}
          <div>
            <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "6px" }}>Source</label>
            <select value={form.from_account_id} onChange={e => setForm(f => ({ ...f, from_account_id: e.target.value }))} style={selStyle}>
              <option value="">Main Pool (Treasury)</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name} — {a.account_number}</option>
              ))}
            </select>
            <div style={{ fontSize: "10px", color: "#444", marginTop: "5px" }}>Leave blank to draw from the main treasury pool</div>
          </div>

          {/* Destination */}
          <div>
            <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "6px" }}>Destination Account *</label>
            <select required value={form.to_account_id} onChange={e => setForm(f => ({ ...f, to_account_id: e.target.value }))} style={selStyle}>
              <option value="">Select destination…</option>
              {accounts.filter(a => a.id !== form.from_account_id).map(a => (
                <option key={a.id} value={a.id}>{a.name} — {a.account_number}</option>
              ))}
            </select>
          </div>

          {/* Amount */}
          <div>
            <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "6px" }}>Amount (₹) *</label>
            <div style={{ position: "relative" }}>
              <span style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "#555", fontSize: "14px", fontWeight: 700 }}>₹</span>
              <input required type="number" min="0.01" step="0.01" placeholder="0.00" value={form.amount}
                onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                style={{ ...inputStyle, paddingLeft: "28px" }} />
            </div>
            <div style={{ fontSize: "10px", color: "#444", marginTop: "5px" }}>Virtual rupees only — no real money is transferred</div>
          </div>

          {/* Description */}
          <div>
            <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "6px" }}>Description / Purpose *</label>
            <textarea required rows={3} placeholder="Explain the purpose of this request…" value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              style={{ ...inputStyle, resize: "vertical" }} />
          </div>

          {error && (
            <div style={{ background: "rgba(151,25,44,0.12)", border: "2px solid #97192c", borderRadius: "3px", padding: "10px 14px", fontSize: "12px", color: "#e57373" }}>
              {error}
            </div>
          )}

          {/* Preview */}
          {form.amount && !isNaN(parseFloat(form.amount)) && (
            <div style={{ background: "rgba(252,146,13,0.06)", border: "2px solid rgba(252,146,13,0.2)", borderRadius: "3px", padding: "12px 14px" }}>
              <div style={{ fontSize: "11px", color: "#888", marginBottom: "4px" }}>Request preview</div>
              <div style={{ fontSize: "18px", fontWeight: 800, color: "#fc920d" }}>
                ₹{parseFloat(form.amount || "0").toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: "11px", color: "#555", marginTop: "3px" }}>
                {form.from_account_id ? "Account Transfer" : "Pool Draw"} → pending admin approval
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: "10px" }}>
            <button type="submit" disabled={submitting}
              style={{ flex: 1, padding: "11px", background: "#fc920d", border: "2px solid #fc920d", borderRadius: "3px", color: "#000", fontWeight: 700, fontSize: "13px", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.6 : 1, boxShadow: "3px 3px 0 0 rgba(252,146,13,0.4)" }}>
              {submitting ? "Submitting…" : "Submit Request"}
            </button>
            <Link href="/finance/requests"
              style={{ flex: 1, padding: "11px", background: "transparent", border: "2px solid #2a2a2a", borderRadius: "3px", color: "#888", fontWeight: 600, fontSize: "13px", textDecoration: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
