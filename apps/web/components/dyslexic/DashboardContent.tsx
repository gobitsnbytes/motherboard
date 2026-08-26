"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  CheckCircle2,
  Clock,
  Mail,
  MessageSquare,
  Trophy,
  Users,
} from "lucide-react";
import StatCard from "components/dashboard/StatCard";
import { useDyslexicStream } from "hooks/useDyslexicStream";
import {
  formatRelative,
  getActivity,
  getFollowUps,
  getLeaderboard,
  getStats,
  resolveFollowUp,
  type FollowUp,
  type LeaderboardRow,
  type Stats,
  type TimelineEvent,
} from "lib/dyslexic";
import { DyslexicTabs, ErrorNote, SectionHeader, StreamIndicator } from "./DyslexicChrome";

export default function DashboardContent() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [activity, setActivity] = useState<TimelineEvent[]>([]);
  const [leaders, setLeaders] = useState<LeaderboardRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [nextStats, nextFollowUps, nextActivity, nextLeaders] = await Promise.all([
        getStats(),
        getFollowUps("mine"),
        getActivity(15),
        getLeaderboard("all"),
      ]);
      setStats(nextStats);
      setFollowUps(nextFollowUps);
      setActivity(nextActivity);
      setLeaders(nextLeaders.slice(0, 5));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const { status } = useDyslexicStream(load);

  async function handleResolve(id: string) {
    // Optimistic — the list is a to-do, and re-appearing on failure is clearer
    // than a spinner on a checkbox.
    setFollowUps((current) => current.filter((item) => item.id !== id));
    try {
      await resolveFollowUp(id);
      load();
    } catch {
      load();
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        title="Dyslexic"
        description="Sponsorship research, outreach, and follow-ups for bits&bytes."
        action={<StreamIndicator status={status} />}
      />
      <DyslexicTabs />

      {error && <ErrorNote message={error} />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Companies"
          value={loading ? "—" : stats?.companies ?? 0}
          icon={<Building2 className="size-4 text-muted-foreground" />}
        />
        <StatCard
          title="Contacts"
          value={loading ? "—" : stats?.contacts ?? 0}
          icon={<Users className="size-4 text-muted-foreground" />}
        />
        <StatCard
          title="Emails Sent"
          value={loading ? "—" : stats?.emails_sent ?? 0}
          icon={<Mail className="size-4 text-muted-foreground" />}
        />
        <StatCard
          title="Replies"
          value={loading ? "—" : stats?.replies ?? 0}
          icon={<MessageSquare className="size-4 text-muted-foreground" />}
        />
        <StatCard
          title="Follow-ups Due"
          value={loading ? "—" : stats?.follow_ups_due ?? 0}
          description="Across the whole team"
          icon={<Clock className="size-4 text-muted-foreground" />}
        />
        <StatCard
          title="Yours Due"
          value={loading ? "—" : stats?.my_follow_ups_due ?? 0}
          description="Assigned to you"
          icon={<Clock className="size-4 text-orange" />}
        />
        <StatCard
          title="Sponsors Closed"
          value={loading ? "—" : stats?.sponsors_closed ?? 0}
          icon={<CheckCircle2 className="size-4 text-green-400" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-base border-2 border-border bg-[#141418] p-5 shadow-dark">
          <h2 className="mb-3 font-heading font-black text-xs uppercase tracking-wider text-white">
            Your follow-ups
          </h2>

          {followUps.length === 0 ? (
            <p className="py-6 text-center text-xs font-mono text-zinc-400">
              {loading ? "Loading…" : "Nothing to chase right now."}
            </p>
          ) : (
            <ul className="flex flex-col gap-2.5">
              {followUps.map((item) => (
                <li
                  key={item.id}
                  className={`flex items-center justify-between gap-3 rounded-base border-2 px-3.5 py-2.5 shadow-light ${
                    item.is_overdue
                      ? "border-orange bg-orange/10"
                      : "border-border bg-[#181820]"
                  }`}
                >
                  <div className="min-w-0">
                    <Link
                      href={`/dashboard/dyslexic/companies/${item.company_id}`}
                      className="block truncate text-xs font-bold text-white hover:text-orange"
                    >
                      {item.contact_name} &bull; {item.company_name}
                    </Link>
                    <p className="text-[11px] font-mono text-zinc-400">
                      {item.is_overdue ? "Overdue — due " : "Due "}
                      {formatRelative(item.due_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleResolve(item.id)}
                    className="shrink-0 rounded-base border-2 border-black bg-orange text-black px-2.5 py-1 text-xs font-mono font-bold hover:translate-x-[1px] hover:translate-y-[1px] shadow-light"
                  >
                    Done
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-base border-2 border-border bg-[#141418] p-5 shadow-dark">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-heading font-black text-xs uppercase tracking-wider text-white">
              Top contributors
            </h2>
            <Link
              href="/dashboard/dyslexic/leaderboard"
              className="text-xs font-mono font-bold text-orange hover:underline"
            >
              View all &rarr;
            </Link>
          </div>

          {leaders.length === 0 ? (
            <p className="py-6 text-center text-xs font-mono text-zinc-400">
              {loading ? "Loading…" : "No contributions yet."}
            </p>
          ) : (
            <ol className="flex flex-col gap-2.5">
              {leaders.map((row, index) => (
                <li
                  key={row.user_id}
                  className="flex items-center gap-3 rounded-base border-2 border-border bg-[#181820] px-3.5 py-2.5 shadow-light"
                >
                  <span className="w-5 text-center font-mono text-xs font-bold text-zinc-400">
                    {index + 1}
                  </span>
                  <Trophy
                    className={`size-4 shrink-0 ${index === 0 ? "text-orange" : "text-zinc-600"}`}
                  />
                  <span className="min-w-0 flex-1 truncate text-xs font-bold text-white">{row.display_name}</span>
                  <span className="font-mono text-xs font-bold text-orange">{row.score}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className="rounded-base border-2 border-border bg-[#141418] p-5 shadow-dark">
        <h2 className="mb-3 font-heading font-black text-xs uppercase tracking-wider text-white">
          Recent activity
        </h2>

        {activity.length === 0 ? (
          <p className="py-6 text-center text-xs font-mono text-zinc-400">
            {loading ? "Loading…" : "Nothing has happened yet."}
          </p>
        ) : (
          <ul className="flex flex-col">
            {activity.map((event) => (
              <li
                key={event.id}
                className="flex items-baseline justify-between gap-4 border-b border-border py-2.5 last:border-0 font-mono text-xs"
              >
                <Link
                  href={`/dashboard/dyslexic/companies/${event.company_id}`}
                  className="min-w-0 flex-1 truncate text-zinc-200 hover:text-orange"
                >
                  {event.summary}
                </Link>
                <span className="shrink-0 text-[11px] text-zinc-400">
                  {formatRelative(event.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
