"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

const API = "";

interface Account {
  id: string; owner_id: string; name: string; description: string | null;
  balance_rupees: number; account_number: string; ifsc: string; is_active: boolean; created_at: string;
}

interface CreateForm { name: string; description: string; owner_id: string; }

const inputClass =
  "box-border w-full rounded-base border-2 border-border bg-background px-3 py-2 font-base text-[13px] text-white outline-none focus:border-orange";

const labelClass =
  "mb-1.5 block font-heading text-[10px] uppercase tracking-[0.12em] text-muted-foreground";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [users, setUsers] = useState<{ id: string; display_name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateForm>({ name: "", description: "", owner_id: "" });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const getHeaders = (): Record<string, string> => ({ "Content-Type": "application/json" });

  const load = () => {
    setLoading(true);
    fetch(`${API}/api/finance/accounts?active_only=false`, { headers: getHeaders() })
      .then((r) => r.json())
      .then((d) => setAccounts(Array.isArray(d) ? d : []))
      .catch(() => setError("Failed to load accounts."))
      .finally(() => setLoading(false));

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
      const res = await fetch(`${API}/api/finance/accounts`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ name: form.name, description: form.description || null, owner_id: form.owner_id }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail ?? "Failed"); }
      setShowCreate(false);
      setForm({ name: "", description: "", owner_id: "" });
      load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create account");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="font-heading">
      <div className="mb-7 flex items-start justify-between">
        <div>
          <h1 className="m-0 font-heading text-[22px] font-extrabold text-white">Virtual Accounts</h1>
          <p className="mt-1 font-base text-xs text-muted-foreground">Paper bank accounts — no real money attached</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="cursor-pointer rounded-base border-2 border-orange bg-orange px-4 py-2 font-heading text-xs font-bold text-black shadow-shadow transition-transform hover:translate-x-[3px] hover:translate-y-[3px] hover:shadow-none">
          + New Account
        </button>
      </div>

      {error && (
        <div className="mb-5 rounded-base border-2 border-burgundy bg-burgundy/10 px-4 py-3 font-base text-[13px] text-red-300 shadow-shadow">
          {error}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="w-[420px] rounded-base border-2 border-orange bg-main p-7"
            style={{ boxShadow: "6px 6px 0 0 rgba(252,146,13,0.3)" }}>
            <h2 className="m-0 mb-5 font-heading text-base font-extrabold text-white">Create Virtual Account</h2>
            <form onSubmit={handleCreate} className="flex flex-col gap-3.5">
              <div>
                <label className={labelClass}>Account Name *</label>
                <input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Delhi Fork Budget" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Description</label>
                <input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Optional description" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Owner *</label>
                {users.length > 0 ? (
                  <select required value={form.owner_id} onChange={(e) => setForm((f) => ({ ...f, owner_id: e.target.value }))} className={`${inputClass} px-2`}>
                    <option value="">Select owner…</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>{u.display_name}</option>
                    ))}
                  </select>
                ) : (
                  <input required value={form.owner_id} onChange={(e) => setForm((f) => ({ ...f, owner_id: e.target.value }))} placeholder="UUID of the account owner" className={inputClass} />
                )}
              </div>
              {formError && <div className="font-base text-xs text-red-500">{formError}</div>}
              <div className="mt-1 flex gap-2.5">
                <button type="submit" disabled={submitting}
                  className={`flex-1 rounded-base border-2 border-orange bg-orange py-2 font-heading text-xs font-bold text-black ${submitting ? "cursor-wait opacity-60" : "cursor-pointer"}`}>
                  {submitting ? "Creating…" : "Create"}
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
        <div className="font-base text-[13px] text-muted-foreground/50">Loading accounts…</div>
      ) : accounts.length === 0 ? (
        <div className="rounded-base border-2 border-dashed border-border p-[60px_20px] text-center font-base text-muted-foreground/50">
          <div className="mb-2 text-sm">No virtual accounts yet</div>
          <div className="text-xs">Create one to start tracking virtual funds</div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {accounts.map((a, i) => (
            <motion.div key={a.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Link href={`/finance/accounts/${a.id}`} className="group block no-underline">
                <div className="relative cursor-pointer rounded-base border-2 border-border bg-main p-5 shadow-shadow transition-all duration-150 group-hover:border-orange group-hover:shadow-[4px_4px_0_0_#fc920d]">
                  <div className={`absolute right-3.5 top-3.5 size-[7px] rounded-full ${a.is_active ? "bg-green-500" : "bg-muted-foreground/50"}`} />
                  <div className="mb-1 font-heading text-sm font-bold text-white/90">{a.name}</div>
                  {a.description && <div className="mb-3 font-base text-[11px] text-muted-foreground">{a.description}</div>}
                  <div className="mb-3.5 font-mono text-[11px] text-muted-foreground/60">
                    {a.account_number.replace(/(\d{4})/g, "$1 ").trim()} · {a.ifsc}
                  </div>
                  <div className={`font-heading text-xl font-extrabold ${a.balance_rupees >= 0 ? "text-green-500" : "text-red-500"}`}>
                    ₹{a.balance_rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </div>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
