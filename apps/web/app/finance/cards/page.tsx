"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

const API = "";

interface Card { id: string; card_name: string; last_four: string; card_type: string; is_active: boolean; expires_year: string; holder_id: string; account_id: string; daily_limit_paise: number | null; monthly_limit_paise: number | null; daily_limit_rupees: number | null; monthly_limit_rupees: number | null; }
interface CreateCardForm { account_id: string; holder_id: string; card_name: string; card_type: "virtual" | "debit"; expires_month: string; expires_year: string; daily_limit_rupees: string; monthly_limit_rupees: string; }

const CARD_GRADIENT: Record<string, string> = {
  virtual: "linear-gradient(135deg, #1e1e1e 0%, #2a1a0a 100%)",
  debit: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
};

export default function CardsPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateCardForm>({ account_id: "", holder_id: "", card_name: "", card_type: "virtual", expires_month: "", expires_year: "", daily_limit_rupees: "", monthly_limit_rupees: "" });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [simulatingCard, setSimulatingCard] = useState<Card | null>(null);
  const [simForm, setSimForm] = useState({ amount_rupees: "", merchant: "", description: "" });
  const [simSubmitting, setSimSubmitting] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);
  const [simSuccess, setSimSuccess] = useState<boolean>(false);

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!simulatingCard) return;
    setSimSubmitting(true);
    setSimError(null);
    setSimSuccess(false);
    try {
      const res = await fetch(`${API}/api/finance/cards/${simulatingCard.id}/simulate-charge`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          amount_paise: Math.round(parseFloat(simForm.amount_rupees) * 100),
          merchant: simForm.merchant,
          description: simForm.description,
        }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail ?? "Transaction declined.");
      }
      setSimSuccess(true);
      setSimForm({ amount_rupees: "", merchant: "", description: "" });
      setTimeout(() => {
        setSimulatingCard(null);
        setSimSuccess(false);
      }, 1500);
      load();
    } catch (err: unknown) {
      setSimError(err instanceof Error ? err.message : "Failed to simulate charge");
    } finally {
      setSimSubmitting(false);
    }
  };

  const getHeaders = (): Record<string, string> => ({ "Content-Type": "application/json" });

  const load = () => {
    setLoading(true);
    fetch(`${API}/api/finance/cards`, { headers: getHeaders() })
      .then(r => r.json())
      .then(d => setCards(Array.isArray(d) ? d : []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const payload: {
        account_id: string;
        holder_id: string;
        card_name: string;
        card_type: string;
        expires_month: number;
        expires_year: number;
        daily_limit_paise?: number;
        monthly_limit_paise?: number;
      } = {
        account_id: form.account_id,
        holder_id: form.holder_id,
        card_name: form.card_name,
        card_type: form.card_type,
        expires_month: parseInt(form.expires_month),
        expires_year: parseInt(form.expires_year),
      };
      if (form.daily_limit_rupees) {
        payload.daily_limit_paise = Math.round(parseFloat(form.daily_limit_rupees) * 100);
      }
      if (form.monthly_limit_rupees) {
        payload.monthly_limit_paise = Math.round(parseFloat(form.monthly_limit_rupees) * 100);
      }

      const res = await fetch(`${API}/api/finance/cards`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail ?? "Failed"); }
      setShowCreate(false);
      setForm({ account_id: "", holder_id: "", card_name: "", card_type: "virtual", expires_month: "", expires_year: "", daily_limit_rupees: "", monthly_limit_rupees: "" });
      load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create card");
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", background: "#0d0d0d", border: "2px solid #2a2a2a", borderRadius: "3px",
    padding: "9px 12px", color: "#fff", fontFamily: "Inter, sans-serif", fontSize: "13px",
    outline: "none", boxSizing: "border-box",
  };

  return (
    <div style={{ fontFamily: "Inter, sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px" }}>
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#fff", margin: 0 }}>Virtual Cards</h1>
          <p style={{ fontSize: "12px", color: "#555", marginTop: "4px" }}>Tracking instruments only — no real payment rails</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          style={{ padding: "9px 16px", background: "#97192c", border: "2px solid #97192c", borderRadius: "3px", color: "#fff", fontWeight: 700, fontSize: "12px", cursor: "pointer", boxShadow: "3px 3px 0 0 rgba(151,25,44,0.4)" }}>
          + Issue Card
        </button>
      </div>

      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            style={{ background: "#111", border: "2px solid #97192c", borderRadius: "4px", padding: "28px", width: "420px", boxShadow: "6px 6px 0 0 rgba(151,25,44,0.3)" }}>
            <h2 style={{ fontSize: "16px", fontWeight: 800, color: "#fff", margin: "0 0 20px" }}>Issue Virtual Card</h2>
            <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {[
                { key: "account_id", label: "Account ID *", placeholder: "UUID of the virtual account" },
                { key: "holder_id", label: "Holder User ID *", placeholder: "UUID of the cardholder" },
                { key: "card_name", label: "Card Name *", placeholder: "e.g. Devaansh Pathak" },
              ].map(({ key, label, placeholder }) => (
                <div key={key}>
                  <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>{label}</label>
                  <input required value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} placeholder={placeholder} style={inputStyle} />
                </div>
              ))}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Daily Limit (₹)</label>
                  <input type="number" placeholder="Optional" value={form.daily_limit_rupees} onChange={e => setForm(f => ({ ...f, daily_limit_rupees: e.target.value }))} style={inputStyle} />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Monthly Limit (₹)</label>
                  <input type="number" placeholder="Optional" value={form.monthly_limit_rupees} onChange={e => setForm(f => ({ ...f, monthly_limit_rupees: e.target.value }))} style={inputStyle} />
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Type *</label>
                  <select required value={form.card_type} onChange={e => setForm(f => ({ ...f, card_type: e.target.value as any }))}
                    style={{ ...inputStyle, padding: "9px 8px" }}>
                    <option value="virtual">Virtual</option>
                    <option value="debit">Debit</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Month *</label>
                  <input required type="number" min="1" max="12" placeholder="MM" value={form.expires_month} onChange={e => setForm(f => ({ ...f, expires_month: e.target.value }))} style={inputStyle} />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Year *</label>
                  <input required type="number" min="2024" max="2040" placeholder="YYYY" value={form.expires_year} onChange={e => setForm(f => ({ ...f, expires_year: e.target.value }))} style={inputStyle} />
                </div>
              </div>
              {formError && <div style={{ fontSize: "12px", color: "#ef4444" }}>{formError}</div>}
              <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
                <button type="submit" disabled={submitting}
                  style={{ flex: 1, padding: "9px", background: "#97192c", border: "2px solid #97192c", borderRadius: "3px", color: "#fff", fontWeight: 700, fontSize: "12px", cursor: "pointer", opacity: submitting ? 0.6 : 1 }}>
                  {submitting ? "Issuing…" : "Issue Card"}
                </button>
                <button type="button" onClick={() => setShowCreate(false)}
                  style={{ flex: 1, padding: "9px", background: "transparent", border: "2px solid #2a2a2a", borderRadius: "3px", color: "#888", fontWeight: 600, fontSize: "12px", cursor: "pointer" }}>
                  Cancel
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {loading ? (
        <div style={{ color: "#333", fontSize: "13px" }}>Loading cards…</div>
      ) : cards.length === 0 ? (
        <div style={{ textAlign: "center", padding: "60px 20px", border: "2px dashed #1e1e1e", borderRadius: "4px", color: "#333" }}>
          <div style={{ fontSize: "14px", marginBottom: "8px" }}>No cards issued yet</div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "20px" }}>
          {cards.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
              style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "8px", padding: "16px", display: "flex", flexDirection: "column", gap: "12px", boxShadow: "4px 4px 0 0 #111" }}>
              <div style={{
                background: CARD_GRADIENT[c.card_type] ?? CARD_GRADIENT.virtual,
                border: `2px solid ${c.card_type === "debit" ? "#97192c" : "#fc920d"}`,
                borderRadius: "6px",
                padding: "20px",
                aspectRatio: "1.586 / 1",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                boxShadow: `2px 2px 0 0 ${c.card_type === "debit" ? "rgba(151,25,44,0.2)" : "rgba(252,146,13,0.2)"}`,
                opacity: c.is_active ? 1 : 0.4,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ fontSize: "9px", color: "#888", textTransform: "uppercase", letterSpacing: "0.15em" }}>{c.card_type}</div>
                  <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: c.is_active ? "#22c55e" : "#555" }} />
                </div>
                <div style={{ fontFamily: "monospace", fontSize: "15px", color: "#ccc", letterSpacing: "0.18em" }}>
                  •••• •••• •••• {c.last_four}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
                  <div>
                    <div style={{ fontSize: "9px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "3px" }}>Cardholder</div>
                    <div style={{ fontSize: "12px", color: "#ddd", fontWeight: 600 }}>{c.card_name}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "9px", color: "#555", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "3px" }}>Exp</div>
                    <div style={{ fontFamily: "monospace", fontSize: "12px", color: "#aaa" }}>{c.expires_year}</div>
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#666" }}>
                  <span>Daily: <strong style={{ color: "#aaa" }}>{c.daily_limit_rupees !== null && c.daily_limit_rupees !== undefined ? `₹${c.daily_limit_rupees}` : "No Limit"}</strong></span>
                  <span>Monthly: <strong style={{ color: "#aaa" }}>{c.monthly_limit_rupees !== null && c.monthly_limit_rupees !== undefined ? `₹${c.monthly_limit_rupees}` : "No Limit"}</strong></span>
                </div>
                <button
                  onClick={() => {
                    setSimulatingCard(c);
                    setSimForm({ amount_rupees: "", merchant: "", description: "" });
                    setSimError(null);
                    setSimSuccess(false);
                  }}
                  disabled={!c.is_active}
                  style={{
                    width: "100%",
                    padding: "7px 0",
                    background: "#080808",
                    border: "2px solid #222",
                    borderRadius: "3px",
                    color: c.is_active ? "#ccc" : "#444",
                    fontSize: "11px",
                    fontWeight: 700,
                    cursor: c.is_active ? "pointer" : "not-allowed",
                    textAlign: "center",
                  }}
                >
                  ⚡ Simulate Charge
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {simulatingCard && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            style={{ background: "#111", border: "2px solid #fc920d", borderRadius: "4px", padding: "28px", width: "420px", boxShadow: "6px 6px 0 0 rgba(252,146,13,0.3)" }}>
            <h2 style={{ fontSize: "16px", fontWeight: 800, color: "#fff", margin: "0 0 10px" }}>Simulate Card Charge</h2>
            <p style={{ fontSize: "12px", color: "#666", marginBottom: "20px" }}>
              Simulate an auth/capture request on card ending in <strong>{simulatingCard.last_four}</strong>.
            </p>
            <form onSubmit={handleSimulate} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Merchant *</label>
                <input required value={simForm.merchant} onChange={e => setSimForm(sf => ({ ...sf, merchant: e.target.value }))} placeholder="e.g. AWS Cloud, Starbucks" style={inputStyle} />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Description *</label>
                <input required value={simForm.description} onChange={e => setSimForm(sf => ({ ...sf, description: e.target.value }))} placeholder="e.g. Monthly hosting subscription" style={inputStyle} />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Amount (₹) *</label>
                <input required type="number" step="0.01" min="0.01" value={simForm.amount_rupees} onChange={e => setSimForm(sf => ({ ...sf, amount_rupees: e.target.value }))} placeholder="0.00" style={inputStyle} />
              </div>
              
              {simError && <div style={{ fontSize: "12px", color: "#ef4444", fontWeight: 600 }}>❌ {simError}</div>}
              {simSuccess && <div style={{ fontSize: "12px", color: "#22c55e", fontWeight: 600 }}>✅ Transaction approved successfully!</div>}
              
              <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
                <button type="submit" disabled={simSubmitting || simSuccess}
                  style={{ flex: 1, padding: "9px", background: "#fc920d", border: "2px solid #fc920d", borderRadius: "3px", color: "#000", fontWeight: 800, fontSize: "12px", cursor: "pointer", opacity: (simSubmitting || simSuccess) ? 0.6 : 1 }}>
                  {simSubmitting ? "Processing…" : simSuccess ? "Success!" : "Authorize Charge"}
                </button>
                <button type="button" onClick={() => setSimulatingCard(null)} disabled={simSubmitting}
                  style={{ flex: 1, padding: "9px", background: "transparent", border: "2px solid #2a2a2a", borderRadius: "3px", color: "#888", fontWeight: 600, fontSize: "12px", cursor: "pointer" }}>
                  Cancel
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </div>
  );
}
