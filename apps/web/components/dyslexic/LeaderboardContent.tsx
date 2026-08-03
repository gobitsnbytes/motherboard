"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Trophy } from "lucide-react";
import { useDyslexicStream } from "hooks/useDyslexicStream";
import { getLeaderboard, type LeaderboardRow } from "lib/dyslexic";
import { DyslexicTabs, ErrorNote, SectionHeader, StreamIndicator } from "./DyslexicChrome";

const COLUMNS = [
  { key: "companies_added", label: "Companies" },
  { key: "contacts_added", label: "Contacts" },
  { key: "emails_sent", label: "Emails" },
  { key: "follow_ups_sent", label: "Follow-ups" },
  { key: "replies_received", label: "Replies" },
  { key: "meetings_scheduled", label: "Meetings" },
  { key: "sponsors_closed", label: "Sponsors" },
] as const;

export default function LeaderboardContent() {
  const { data: session } = useSession();
  const myId = session?.user?.internalUserId;

  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [period, setPeriod] = useState<"all" | "30d">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await getLeaderboard(period));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the leaderboard.");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    load();
  }, [load]);

  const { status } = useDyslexicStream(load);

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        title="Leaderboard"
        description="Counted from the outreach records themselves — nobody tracks this by hand."
        action={<StreamIndicator status={status} />}
      />
      <DyslexicTabs />

      {error && <ErrorNote message={error} />}

      <div className="flex gap-2">
        {(["all", "30d"] as const).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setPeriod(value)}
            className={`rounded-base border-2 px-3 py-1.5 text-sm font-medium transition-all ${
              period === value
                ? "border-border bg-main text-main-foreground shadow-light"
                : "border-border hover:bg-white/5"
            }`}
          >
            {value === "all" ? "All time" : "Last 30 days"}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-base border-2 border-border">
        <table className="w-full min-w-[820px]">
          <thead>
            <tr className="border-b-2 border-border bg-[#111] text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-heading">#</th>
              <th className="px-4 py-3 font-heading">Volunteer</th>
              {COLUMNS.map((column) => (
                <th key={column.key} className="px-3 py-3 text-right font-heading">
                  {column.label}
                </th>
              ))}
              <th className="px-4 py-3 text-right font-heading">Score</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="p-8 text-center text-sm text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={10} className="p-8 text-center text-sm text-muted-foreground">
                  No contributions in this period yet.
                </td>
              </tr>
            ) : (
              rows.map((row, index) => {
                const isMe = myId && row.user_id === myId;
                return (
                  <tr
                    key={row.user_id}
                    className={`border-b border-border/50 last:border-0 ${
                      isMe ? "bg-main/10" : "hover:bg-white/5"
                    }`}
                  >
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5 font-heading text-sm font-bold">
                        {index + 1}
                        {index === 0 && <Trophy className="size-3.5 text-orange" />}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">
                      {row.display_name}
                      {isMe && (
                        <span className="ml-2 text-xs text-muted-foreground">you</span>
                      )}
                    </td>
                    {COLUMNS.map((column) => (
                      <td
                        key={column.key}
                        className="px-3 py-3 text-right text-sm text-muted-foreground"
                      >
                        {row[column.key]}
                      </td>
                    ))}
                    <td className="px-4 py-3 text-right font-heading text-sm font-bold">
                      {row.score}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">
        Score weights outcomes above volume: a closed sponsor counts for twenty, a
        company added counts for one.
      </p>
    </div>
  );
}
