"use client";

import { Card, CardContent, CardHeader, CardTitle, Input } from "@bnb/ui";
import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getAuditLogs } from "lib/audit";

export function AuditContent() {
  const [search, setSearch] = useState("");
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    getAuditLogs()
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);
  const filteredLogs = useMemo(() => {
    return logs.filter((log) =>
      log.action?.toLowerCase().includes(search.toLowerCase()),
    );
  }, [logs, search]);
  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Total Events</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {loading ? "..." : logs.length}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Events</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {loading ? "..." : Math.min(logs.length, 10)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-3xl font-bold">
              {loading ? "..." : filteredLogs.length}
            </p>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">--</p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />

        <Input
          placeholder="Search audit actions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-[#111] text-white placeholder:text-white/50"
        />
      </div>

      {/* Table Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Audit Events</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-left">Action</th>

                  <th className="px-4 py-3 text-left">Actor</th>

                  <th className="px-4 py-3 text-left">Date</th>
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={3} className="p-6 text-center">
                      Loading...
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => (
                    <tr key={log.id} className="border-b border-border">
                      <td className="px-4 py-3">{log.action}</td>

                      <td className="px-4 py-3">{log.actor_id || "-"}</td>

                      <td className="px-4 py-3">
                        {new Date(log.created_at).toLocaleString()}
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
