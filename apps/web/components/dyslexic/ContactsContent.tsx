"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { useDyslexicStream } from "hooks/useDyslexicStream";
import { formatDate, getContacts, type Contact } from "lib/dyslexic";
import { DyslexicTabs, ErrorNote, SectionHeader, StreamIndicator } from "./DyslexicChrome";

const STATUS_FILTERS = [
  { value: "", label: "Everyone" },
  { value: "new", label: "Not contacted" },
  { value: "contacted", label: "Awaiting reply" },
  { value: "replied", label: "Replied" },
  { value: "meeting_scheduled", label: "Meeting scheduled" },
  { value: "sponsored", label: "Sponsored" },
  { value: "rejected", label: "Rejected" },
];

export default function ContactsContent() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setContacts(await getContacts({ status: status || undefined }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load contacts.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const { status: streamStatus } = useDyslexicStream(load);

  const visible = contacts.filter((contact) => {
    const needle = search.trim().toLowerCase();
    if (!needle) return true;
    return (
      contact.name.toLowerCase().includes(needle) ||
      (contact.email ?? "").toLowerCase().includes(needle) ||
      (contact.company_name ?? "").toLowerCase().includes(needle)
    );
  });

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        title="Contacts"
        description="Everyone across every company — find who still needs an email."
        action={<StreamIndicator status={streamStatus} />}
      />
      <DyslexicTabs />

      {error && <ErrorNote message={error} />}

      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, email, or company…"
            className="w-full rounded-base border-2 border-border bg-[#111] py-2 pl-10 pr-3 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-main"
          />
        </div>

        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="rounded-base border-2 border-border bg-[#111] px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-main"
        >
          {STATUS_FILTERS.map((filter) => (
            <option key={filter.value} value={filter.value}>
              {filter.label}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-base border-2 border-border">
        <table className="w-full min-w-[760px]">
          <thead>
            <tr className="border-b-2 border-border bg-[#111] text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-heading">Contact</th>
              <th className="px-4 py-3 font-heading">Company</th>
              <th className="px-4 py-3 font-heading">Status</th>
              <th className="px-4 py-3 font-heading">Contacted by</th>
              <th className="px-4 py-3 font-heading">When</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="p-8 text-center text-sm text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-8 text-center text-sm text-muted-foreground">
                  {contacts.length === 0
                    ? "No contacts yet."
                    : "Nothing matches that search."}
                </td>
              </tr>
            ) : (
              visible.map((contact) => (
                <tr
                  key={contact.id}
                  className="border-b border-border/50 transition-colors last:border-0 hover:bg-white/5"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium">{contact.name}</span>
                    <span className="block text-xs text-muted-foreground">
                      {contact.role ?? contact.email ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <Link
                      href={`/dashboard/dyslexic/companies/${contact.company_id}`}
                      className="hover:text-orange"
                    >
                      {contact.company_name ?? "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={contact.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {contact.contacted_by_name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatDate(contact.contacted_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    new: "bg-white/5 text-white/60 border-white/20",
    contacted: "bg-blue-500/15 text-blue-400 border-blue-500/40",
    replied: "bg-blue-500/15 text-blue-400 border-blue-500/40",
    meeting_scheduled: "bg-orange/15 text-orange border-orange/40",
    sponsored: "bg-green-500/15 text-green-400 border-green-500/40",
    rejected: "bg-red-500/15 text-red-400 border-red-500/40",
    no_reply: "bg-white/5 text-white/50 border-white/20",
    bounced: "bg-red-500/15 text-red-400 border-red-500/40",
  };

  return (
    <span
      className={`inline-block rounded-base border px-2 py-0.5 text-xs whitespace-nowrap ${
        styles[status] ?? styles.new
      }`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
