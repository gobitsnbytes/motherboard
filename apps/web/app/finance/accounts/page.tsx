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

  const inputStyle: React.CSSProperties = {
    width: "100%", background: "#0d0d0d", border: "2px solid #2a2a2a", borderRadius: "3px",
    padding: "9px 12px", color: "#fff", fontFamily: "Inter, sans-serif", fontSize: "13px",
    outline: "none", boxSizing: "border-box",
  };

  return (
    <div style={{ fontFamily: "Inter, sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px" }}>
        <div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#fff", margin: 0 }}>Virtual Accounts</h1>
          <p style={{ fontSize: "12px", color: "#555", marginTop: "4px" }}>Paper bank accounts — no real money attached</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          style={{ padding: "9px 16px", background: "#fc920d", border: "2px solid #fc920d", borderRadius: "3px", color: "#000", fontWeight: 700, fontSize: "12px", cursor: "pointer", boxShadow: "3px 3px 0 0 rgba(252,146,13,0.4)" }}>
          + New Account
        </button>
      </div>

      {error && <div style={{ background: "rgba(151,25,44,0.12)", border: "2px solid #97192c", borderRadius: "4px", padding: "12px 16px", marginBottom: "20px", fontSize: "13px", color: "#e57373" }}>{error}</div>}

      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            style={{ background: "#111", border: "2px solid #fc920d", borderRadius: "4px", padding: "28px", width: "420px", boxShadow: "6px 6px 0 0 rgba(252,146,13,0.3)" }}>
            <h2 style={{ fontSize: "16px", fontWeight: 800, color: "#fff", margin: "0 0 20px" }}>Create Virtual Account</h2>
            <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Account Name *</label>
                <input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Delhi Fork Budget" style={inputStyle} />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Description</label>
                <input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Optional description" style={inputStyle} />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "10px", color: "#888", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "5px" }}>Owner *</label>
                {users.length > 0 ? (
                  <select required value={form.owner_id} onChange={(e) => setForm((f) => ({ ...f, owner_id: e.target.value }))} style={{ ...inputStyle, padding: "9px 8px" }}>
                    <option value="">Select owner…</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>{u.display_name}</option>
                    ))}
                  </select>
                ) : (
                  <input required value={form.owner_id} onChange={(e) => setForm((f) => ({ ...f, owner_id: e.target.value }))} placeholder="UUID of the account owner" style={inputStyle} />
                )}
              </div>
              {formError && <div style={{ fontSize: "12px", color: "#ef4444" }}>{formError}</div>}
              <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
                <button type="submit" disabled={submitting}
                  style={{ flex: 1, padding: "9px", background: "#fc920d", border: "2px solid #fc920d", borderRadius: "3px", color: "#000", fontWeight: 700, fontSize: "12px", cursor: "pointer", opacity: submitting ? 0.6 : 1 }}>
                  {submitting ? "Creating…" : "Create"}
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
        <div style={{ color: "#333", fontSize: "13px" }}>Loading accounts…</div>
      ) : accounts.length === 0 ? (
        <div style={{ textAlign: "center", padding: "60px 20px", border: "2px dashed #1e1e1e", borderRadius: "4px", color: "#333" }}>
          <div style={{ fontSize: "14px", marginBottom: "8px" }}>No virtual accounts yet</div>
          <div style={{ fontSize: "12px" }}>Create one to start tracking virtual funds</div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
          {accounts.map((a, i) => (
            <motion.div key={a.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Link href={`/finance/accounts/${a.id}`} style={{ textDecoration: "none" }}>
                <div
                  style={{ background: "#111", border: "2px solid #1e1e1e", borderRadius: "4px", padding: "20px", cursor: "pointer", boxShadow: "4px 4px 0 0 #0a0a0a", transition: "box-shadow 150ms, border-color 150ms", position: "relative" }}
                  onMouseEnter={(e) => { const el = e.currentTarget as HTMLDivElement; el.style.boxShadow = "4px 4px 0 0 #fc920d"; el.style.borderColor = "#fc920d"; }}
                  onMouseLeave={(e) => { const el = e.currentTarget as HTMLDivElement; el.style.boxShadow = "4px 4px 0 0 #0a0a0a"; el.style.borderColor = "#1e1e1e"; }}
                >
                  <div style={{ position: "absolute", top: "14px", right: "14px", width: "7px", height: "7px", borderRadius: "50%", background: a.is_active ? "#22c55e" : "#555" }} />
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#eee", marginBottom: "4px" }}>{a.name}</div>
                  {a.description && <div style={{ fontSize: "11px", color: "#555", marginBottom: "12px" }}>{a.description}</div>}
                  <div style={{ fontFamily: "monospace", fontSize: "11px", color: "#444", marginBottom: "14px" }}>
                    {a.account_number.replace(/(\d{4})/g, "$1 ").trim()} · {a.ifsc}
                  </div>
                  <div style={{ fontSize: "20px", fontWeight: 800, color: a.balance_rupees >= 0 ? "#22c55e" : "#ef4444" }}>
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
