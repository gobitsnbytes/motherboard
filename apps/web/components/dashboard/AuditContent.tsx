"use client";

import { Card, CardContent, CardHeader, CardTitle, Input, Skeleton } from "@bnb/ui";
import { AlertCircle, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getAuditLogs } from "lib/audit";

interface AuditLog {
  id: string;
  action: string;
  actor_user_id?: string | null;
  actor_id?: string | null;
  actor?: string | null;
  created_at: string;
}

export function AuditContent() {
  const [search, setSearch] = useState("");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
    return logs.filter((log) =>
      log.action?.toLowerCase().includes(search.toLowerCase()),
    );
  }, [logs, search]);
  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="pb-2">
            <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-zinc-400">Total Events</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-heading font-black text-white">
              {loading ? "..." : logs.length}
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="pb-2">
            <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-zinc-400">Recent Window</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-heading font-black text-white">
              {loading ? "..." : Math.min(logs.length, 10)}
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-border bg-[#141418] shadow-light">
          <CardHeader className="pb-2">
            <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-zinc-400">Filtered Events</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-heading font-black text-white">
              {loading ? "..." : filteredLogs.length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-zinc-500" />
        <Input
          placeholder="Search audit actions, events, or resources..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-black border-2 border-border text-white placeholder:text-zinc-500 font-mono text-xs shadow-light focus:outline-none focus:border-orange"
        />
      </div>

      {error ? (
        <div role="alert" className="flex items-center justify-between gap-4 border-2 border-red-700 bg-red-50 p-4 text-sm text-red-900">
          <span className="flex items-center gap-2"><AlertCircle className="size-4" aria-hidden="true" />{error}</span>
          <button type="button" onClick={() => void loadLogs()} className="font-bold underline">Try again</button>
        </div>
      ) : null}

      {/* Table */}
      <Card className="border-2 border-border bg-[#141418] shadow-dark rounded-base overflow-hidden">
        <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
          <CardTitle className="font-heading font-black text-sm uppercase tracking-wider text-white">Audit Event Ledger</CardTitle>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <caption className="sr-only">Administrative audit events</caption>
              <thead>
                <tr className="border-b-2 border-border bg-[#121216] text-zinc-400 uppercase text-[11px] font-bold">
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Timestamp</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr>
                    <td colSpan={3} className="p-6 text-center text-zinc-400">
                      <Skeleton className="mx-auto h-5 w-3/4" />
                    </td>
                  </tr>
                ) : filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="p-6 text-center text-zinc-400">
                      No audit events matched your search.
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => (
                    <tr key={log.id || log.created_at} className="hover:bg-[#181820] transition-colors">
                      <td className="px-4 py-3 font-bold text-orange">{log.action}</td>
                      <td className="px-4 py-3 text-white">{log.actor_user_id || log.actor_id || log.actor || "system"}</td>
                      <td className="px-4 py-3 text-zinc-400">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : "-"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
