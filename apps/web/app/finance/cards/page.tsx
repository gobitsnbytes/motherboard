"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

const API = "";

interface Card { id: string; card_name: string; last_four: string; card_type: string; is_active: boolean; expires_year: string; holder_id: string; account_id: string; daily_limit_paise: number | null; monthly_limit_paise: number | null; daily_limit_rupees: number | null; monthly_limit_rupees: number | null; }
interface CreateCardForm { account_id: string; holder_id: string; card_name: string; card_type: "virtual" | "debit"; expires_month: string; expires_year: string; daily_limit_rupees: string; monthly_limit_rupees: string; }

const inputClass =
  "box-border w-full rounded-base border-2 border-border bg-background px-3 py-2 font-base text-[13px] text-foreground outline-none focus:border-orange";

const labelClass =
  "mb-1.5 block font-heading text-[10px] uppercase tracking-[0.12em] text-muted-foreground";

export default function CardsPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [accounts, setAccounts] = useState<{ id: string; name: string }[]>([]);
  const [users, setUsers] = useState<{ id: string; display_name: string }[]>([]);
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

    fetch(`${API}/api/finance/accounts`, { headers: getHeaders() })
      .then((r) => r.json())
      .then((d) => setAccounts(Array.isArray(d) ? d : []))
      .catch(() => {});

    fetch(`${API}/api/users`, { headers: getHeaders() })
      .then((r) => r.json())
      .then((d) => setUsers(Array.isArray(d) ? d : []))
      .catch(() => {});
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

  return (
    <div className="font-heading">
      <div className="mb-7 flex items-start justify-between">
        <div>
          <h1 className="m-0 font-heading text-[22px] font-extrabold text-foreground">Virtual Cards</h1>
          <p className="mt-1 font-base text-xs text-muted-foreground">Tracking instruments only — no real payment rails</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="cursor-pointer rounded-base border-2 border-burgundy bg-burgundy px-4 py-2 font-heading text-xs font-bold text-white shadow-shadow transition-transform hover:translate-x-[3px] hover:translate-y-[3px] hover:shadow-none">
          + Issue Card
        </button>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="w-[420px] rounded-base border-2 border-burgundy bg-main p-7"
            style={{ boxShadow: "6px 6px 0 0 rgba(151,25,44,0.3)" }}>
            <h2 className="m-0 mb-5 font-heading text-base font-extrabold text-foreground">Issue Virtual Card</h2>
            <form onSubmit={handleCreate} className="flex flex-col gap-3.5">
              <div>
                <label className={labelClass}>Account *</label>
                {accounts.length > 0 ? (
                  <select required value={form.account_id} onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))} className={`${inputClass} px-2`}>
                    <option value="">Select virtual account…</option>
                    {accounts.map(a => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                ) : (
                  <input required value={form.account_id} onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))} placeholder="UUID of the virtual account" className={inputClass} />
                )}
              </div>
              <div>
                <label className={labelClass}>Holder *</label>
                {users.length > 0 ? (
                  <select required value={form.holder_id} onChange={e => {
                    const userId = e.target.value;
                    const matchedUser = users.find(u => u.id === userId);
                    setForm(f => ({
                      ...f,
                      holder_id: userId,
                      card_name: matchedUser ? matchedUser.display_name : f.card_name
                    }));
                  }} className={`${inputClass} px-2`}>
                    <option value="">Select cardholder…</option>
                    {users.map(u => (
                      <option key={u.id} value={u.id}>{u.display_name}</option>
                    ))}
                  </select>
                ) : (
                  <input required value={form.holder_id} onChange={e => setForm(f => ({ ...f, holder_id: e.target.value }))} placeholder="UUID of the cardholder" className={inputClass} />
                )}
              </div>
              <div>
                <label className={labelClass}>Card Name *</label>
                <input required value={form.card_name} onChange={e => setForm(f => ({ ...f, card_name: e.target.value }))} placeholder="e.g. Devaansh Pathak" className={inputClass} />
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className={labelClass}>Daily Limit (₹)</label>
                  <input type="number" placeholder="Optional" value={form.daily_limit_rupees} onChange={e => setForm(f => ({ ...f, daily_limit_rupees: e.target.value }))} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Monthly Limit (₹)</label>
                  <input type="number" placeholder="Optional" value={form.monthly_limit_rupees} onChange={e => setForm(f => ({ ...f, monthly_limit_rupees: e.target.value }))} className={inputClass} />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className={labelClass}>Type *</label>
                  <select required value={form.card_type} onChange={e => setForm(f => ({ ...f, card_type: e.target.value as any }))}
                    className={`${inputClass} px-2`}>
                    <option value="virtual">Virtual</option>
                    <option value="debit">Debit</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Month *</label>
                  <input required type="number" min="1" max="12" placeholder="MM" value={form.expires_month} onChange={e => setForm(f => ({ ...f, expires_month: e.target.value }))} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Year *</label>
                  <input required type="number" min="2024" max="2040" placeholder="YYYY" value={form.expires_year} onChange={e => setForm(f => ({ ...f, expires_year: e.target.value }))} className={inputClass} />
                </div>
              </div>
              {formError && <div className="font-base text-xs text-red-500">{formError}</div>}
              <div className="mt-1 flex gap-2.5">
                <button type="submit" disabled={submitting}
                  className={`flex-1 rounded-base border-2 border-burgundy bg-burgundy py-2 font-heading text-xs font-bold text-white ${submitting ? "cursor-wait opacity-60" : "cursor-pointer"}`}>
                  {submitting ? "Issuing…" : "Issue Card"}
                </button>
                <button type="button" onClick={() => setShowCreate(false)}
                  className="flex-1 cursor-pointer rounded-base border-2 border-border bg-transparent py-2 font-heading text-xs font-semibold text-muted-foreground">
                  Cancel
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {loading ? (
        <div className="font-base text-[13px] text-muted-foreground/50">Loading cards…</div>
      ) : cards.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-border p-[60px_20px] text-center font-base text-muted-foreground/50">
          <div className="mb-2 text-sm">No cards issued yet</div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-5">
          {cards.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
              className="flex flex-col gap-3 rounded-base border-2 border-border bg-main p-4 shadow-shadow">
              <div
                className="flex aspect-[1.586/1] flex-col justify-between rounded-base border-2 p-5"
                style={{
                  background: c.card_type === "debit"
                    ? "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)"
                    : "linear-gradient(135deg, #1e1e1e 0%, #2a1a0a 100%)",
                  borderColor: c.card_type === "debit" ? "#97192c" : "#fc920d",
                  boxShadow: `2px 2px 0 0 ${c.card_type === "debit" ? "rgba(151,25,44,0.2)" : "rgba(252,146,13,0.2)"}`,
                  opacity: c.is_active ? 1 : 0.4,
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="font-heading text-[9px] uppercase tracking-[0.15em] text-muted-foreground">{c.card_type}</div>
                  <div className={`size-2 rounded-full ${c.is_active ? "bg-green-500" : "bg-muted-foreground/50"}`} />
                </div>
                <div className="font-mono text-[15px] tracking-[0.18em] text-white/75">
                  •••• •••• •••• {c.last_four}
                </div>
                <div className="flex items-end justify-between">
                  <div>
                    <div className="mb-0.5 font-heading text-[9px] uppercase tracking-[0.1em] text-muted-foreground">Cardholder</div>
                    <div className="font-heading text-xs font-semibold text-white/85">{c.card_name}</div>
                  </div>
                  <div className="text-right">
                    <div className="mb-0.5 font-heading text-[9px] uppercase tracking-[0.1em] text-muted-foreground">Exp</div>
                    <div className="font-mono text-xs text-white/60">{c.expires_year}</div>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <div className="flex justify-between font-heading text-[11px] text-muted-foreground">
                  <span>Daily: <strong className="text-foreground">{c.daily_limit_rupees !== null && c.daily_limit_rupees !== undefined ? `₹${c.daily_limit_rupees}` : "No Limit"}</strong></span>
                  <span>Monthly: <strong className="text-foreground">{c.monthly_limit_rupees !== null && c.monthly_limit_rupees !== undefined ? `₹${c.monthly_limit_rupees}` : "No Limit"}</strong></span>
                </div>
                <button
                  onClick={() => {
                    setSimulatingCard(c);
                    setSimForm({ amount_rupees: "", merchant: "", description: "" });
                    setSimError(null);
                    setSimSuccess(false);
                  }}
                  disabled={!c.is_active}
                  className={`w-full rounded-base border-2 border-border bg-background py-1.5 font-heading text-[11px] font-bold ${c.is_active ? "cursor-pointer text-foreground hover:border-orange hover:text-orange" : "cursor-not-allowed text-muted-foreground/40"}`}
                >
                  ⚡ Simulate Charge
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {simulatingCard && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="w-[420px] rounded-base border-2 border-orange bg-main p-7"
            style={{ boxShadow: "6px 6px 0 0 rgba(252,146,13,0.3)" }}>
            <h2 className="m-0 mb-2.5 font-heading text-base font-extrabold text-foreground">Simulate Card Charge</h2>
            <p className="mb-5 font-base text-xs text-muted-foreground">
              Simulate an auth/capture request on card ending in <strong>{simulatingCard.last_four}</strong>.
            </p>
            <form onSubmit={handleSimulate} className="flex flex-col gap-3.5">
              <div>
                <label className={labelClass}>Merchant *</label>
                <input required value={simForm.merchant} onChange={e => setSimForm(sf => ({ ...sf, merchant: e.target.value }))} placeholder="e.g. AWS Cloud, Starbucks" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Description *</label>
                <input required value={simForm.description} onChange={e => setSimForm(sf => ({ ...sf, description: e.target.value }))} placeholder="e.g. Monthly hosting subscription" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Amount (₹) *</label>
                <input required type="number" step="0.01" min="0.01" value={simForm.amount_rupees} onChange={e => setSimForm(sf => ({ ...sf, amount_rupees: e.target.value }))} placeholder="0.00" className={inputClass} />
              </div>

              {simError && <div className="font-base text-xs font-semibold text-red-500">❌ {simError}</div>}
              {simSuccess && <div className="font-base text-xs font-semibold text-green-500">✅ Transaction approved successfully!</div>}

              <div className="mt-1 flex gap-2.5">
                <button type="submit" disabled={simSubmitting || simSuccess}
                  className={`flex-1 rounded-base border-2 border-orange bg-orange py-2 font-heading text-xs font-extrabold text-black ${(simSubmitting || simSuccess) ? "cursor-wait opacity-60" : "cursor-pointer"}`}>
                  {simSubmitting ? "Processing…" : simSuccess ? "Success!" : "Authorize Charge"}
                </button>
                <button type="button" onClick={() => setSimulatingCard(null)} disabled={simSubmitting}
                  className="flex-1 cursor-pointer rounded-base border-2 border-border bg-transparent py-2 font-heading text-xs font-semibold text-muted-foreground">
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
