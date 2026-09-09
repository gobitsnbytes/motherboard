"use client";

import { Input, Skeleton } from "@bnb/ui";
import { AlertCircle, Search, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getAuditLogs } from "lib/audit";

interface AuditLog {
  id: string;
  action: string;
  actor_id?: string | null;
  created_at: string;
}

export function AuditContent() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      setLogs((await getAuditLogs()) as AuditLog[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load audit events.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadLogs(); }, []);

  const filteredLogs = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return logs;
    return logs.filter((log) => `${log.action} ${log.actor_id ?? ""}`.toLowerCase().includes(query));
  }, [logs, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-2 border-border bg-background p-5 shadow-shadow sm:flex-row sm:items-center sm:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#97192c]">Accountability trail</p><h2 className="mt-1 font-heading text-xl font-bold">Every important action leaves a trace.</h2><p className="mt-1 text-sm text-muted-foreground">Use this log to understand what changed, who changed it, and when.</p></div>
        <div className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="size-4 text-[#97192c]" aria-hidden="true" />{loading ? "Loading" : `${logs.length} events`}</div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {[["Total events", logs.length], ["Showing", filteredLogs.length], ["Window", "50 max"]].map(([label, value]) => <div key={label} className="border-2 border-border bg-background p-4 shadow-[3px_3px_0_#120f0a]"><p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-2 font-heading text-2xl font-bold">{loading ? "—" : value}</p></div>)}
      </div>

      <label className="relative block max-w-md"><span className="sr-only">Search audit events</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /><Input placeholder="Search action or actor" value={search} onChange={(event) => setSearch(event.target.value)} className="pl-10" /></label>

      {error ? <div role="alert" className="flex items-center justify-between gap-4 border-2 border-red-700 bg-red-50 p-4 text-sm text-red-900"><span className="flex items-center gap-2"><AlertCircle className="size-4" aria-hidden="true" />{error}</span><button type="button" onClick={() => void loadLogs()} className="font-bold underline">Try again</button></div> : null}

      <div className="overflow-hidden border-2 border-border bg-background shadow-shadow"><table className="w-full text-sm"><caption className="sr-only">Administrative audit events</caption><thead className="bg-[#120f0a] text-left text-xs uppercase tracking-wide text-white"><tr><th className="px-4 py-3">Action</th><th className="px-4 py-3">Actor</th><th className="px-4 py-3">Date</th></tr></thead><tbody>
        {loading ? Array.from({ length: 4 }, (_, index) => <tr key={index} className="border-b border-border"><td colSpan={3} className="p-4"><Skeleton className="h-5 w-full" /></td></tr>) : null}
        {!loading && filteredLogs.length === 0 ? <tr><td colSpan={3} className="p-10 text-center text-muted-foreground">{search ? `No events match “${search}”.` : "No audit events recorded yet."}</td></tr> : null}
        {!loading ? filteredLogs.map((log) => <tr key={log.id} className="border-b border-border last:border-0 hover:bg-[#97192c]/5"><td className="px-4 py-3 font-semibold">{log.action}</td><td className="px-4 py-3 font-mono text-xs text-muted-foreground">{log.actor_id || "System"}</td><td className="px-4 py-3 text-muted-foreground">{new Date(log.created_at).toLocaleString()}</td></tr>) : null}
      </tbody></table></div>
    </div>
  );
}
