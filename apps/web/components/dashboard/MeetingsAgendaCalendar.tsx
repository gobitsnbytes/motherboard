"use client";

import React, { useMemo, useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";

// Structural subset of the Meeting shape returned by GET /api/meetings.
export interface AgendaMeeting {
  id: string;
  title: string;
  scheduled_time: number;
  end_time?: number | null;
  status: string;
}

interface MeetingsAgendaCalendarProps {
  meetings: AgendaMeeting[];
  loading: boolean;
  onSelectMeeting: (meeting: AgendaMeeting) => void;
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const MAX_CHIPS = 3;

interface CalendarCell {
  date: Date;
  inMonth: boolean;
  key: string;
}

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function chipTone(status: string): string {
  switch (status) {
    case "active":
      return "bg-emerald-50 text-emerald-800 border-emerald-600";
    case "scheduled":
      return "bg-orange/15 text-orange border-orange/60";
    case "completed":
      return "bg-muted text-muted-foreground border-border";
    case "cancelled":
      return "bg-red-50 text-red-800 border-red-600";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

function formatChipTime(epoch: number): string {
  return new Date(epoch).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function fullDateLabel(d: Date): string {
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function buildMonthCells(year: number, month: number): CalendarCell[] {
  const lead = (new Date(year, month, 1).getDay() + 6) % 7; // Monday-start offset
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const totalCells = Math.ceil((lead + daysInMonth) / 7) * 7;
  const cells: CalendarCell[] = [];
  for (let i = 0; i < totalCells; i++) {
    const date = new Date(year, month, 1 - lead + i);
    cells.push({ date, inMonth: date.getMonth() === month, key: `${dayKey(date)}-${i}` });
  }
  return cells;
}

export default function MeetingsAgendaCalendar({ meetings, loading, onSelectMeeting }: MeetingsAgendaCalendarProps) {
  const now = new Date();
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() });

  const cells = useMemo(() => buildMonthCells(cursor.year, cursor.month), [cursor]);

  const meetingsByDay = useMemo(() => {
    const map = new Map<string, AgendaMeeting[]>();
    for (const m of meetings ?? []) {
      if (!m?.scheduled_time) continue;
      const d = new Date(m.scheduled_time);
      const key = dayKey(d);
      const list = map.get(key);
      if (list) list.push(m);
      else map.set(key, [m]);
    }
    for (const list of map.values()) {
      list.sort((a, b) => a.scheduled_time - b.scheduled_time);
    }
    return map;
  }, [meetings]);

  const todayKey = dayKey(now);

  const prevMonth = () => {
    setCursor(({ year, month }) =>
      month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 }
    );
  };

  const nextMonth = () => {
    setCursor(({ year, month }) =>
      month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 }
    );
  };

  const goToday = () => {
    const t = new Date();
    setCursor({ year: t.getFullYear(), month: t.getMonth() });
  };

  if (loading) {
    return (
      <div className="border-4 border-border bg-secondary-background rounded-base p-4 shadow-shadow" role="status" aria-label="Loading calendar">
        <div className="h-6 w-48 bg-muted rounded-base animate-pulse motion-reduce:animate-none mb-4" />
        <div className="grid grid-cols-7 gap-1 min-w-[640px]">
          {[...Array(35)].map((_, i) => (
            <div
              key={i}
              className="min-h-[72px] sm:min-h-[96px] border-2 border-border rounded-base bg-muted animate-pulse motion-reduce:animate-none"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header: month navigation */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-2 border-border bg-secondary-background rounded-base px-4 py-3 shadow-shadow">
        <h2 className="text-lg font-heading font-black text-foreground uppercase tracking-tight">
          {MONTHS[cursor.month]} {cursor.year}
        </h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={prevMonth}
            aria-label={`Previous month (${MONTHS[(cursor.month + 11) % 12]} ${cursor.month === 0 ? cursor.year - 1 : cursor.year})`}
            className="p-1.5 border-2 border-border bg-muted text-foreground rounded-base hover:bg-secondary-background transition-colors duration-150 motion-reduce:transition-none"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            type="button"
            onClick={goToday}
            className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-border bg-orange text-black font-heading font-bold rounded-base text-xs uppercase tracking-wider hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none shadow-[2px_2px_0px_0px_var(--border)] transition-all duration-150 motion-reduce:transition-none"
          >
            <CalendarClock className="size-3.5 shrink-0" />
            Today
          </button>
          <button
            type="button"
            onClick={nextMonth}
            aria-label={`Next month (${MONTHS[(cursor.month + 1) % 12]} ${cursor.month === 11 ? cursor.year + 1 : cursor.year})`}
            className="p-1.5 border-2 border-border bg-muted text-foreground rounded-base hover:bg-secondary-background transition-colors duration-150 motion-reduce:transition-none"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>

      {/* Grid wrapper: horizontal scroll guard on narrow screens */}
      <div className="border-4 border-border bg-secondary-background rounded-base p-3 shadow-shadow overflow-x-auto">
        <div className="min-w-[640px]">
          {/* Weekday headers */}
          <div className="grid grid-cols-7 gap-1 mb-1" role="row">
            {WEEKDAYS.map((wd) => (
              <div key={wd} className="text-center text-[10px] font-heading font-black text-muted-foreground uppercase tracking-widest py-1">
                {wd}
              </div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7 gap-1">
            {cells.map(({ date, inMonth, key }) => {
              const dayMeetings = meetingsByDay.get(dayKey(date)) ?? [];
              const isToday = dayKey(date) === todayKey;
              const interactive = inMonth && dayMeetings.length > 0;
              const visible = dayMeetings.slice(0, MAX_CHIPS);
              const hiddenCount = dayMeetings.length - visible.length;

              const handleSelect = () => {
                const first = interactive ? dayMeetings[0] : undefined;
                if (first) onSelectMeeting(first);
              };

              const cellClasses = [
                "relative flex flex-col gap-1 p-1.5 rounded-base border-2 transition-colors duration-150 motion-reduce:transition-none",
                isToday ? "border-orange" : "border-border",
                inMonth ? "bg-background" : "bg-transparent opacity-40",
                interactive
                  ? "cursor-pointer hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
                  : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <div
                  key={key}
                  role={interactive ? "button" : undefined}
                  tabIndex={interactive ? 0 : -1}
                  aria-label={
                    interactive
                      ? `${fullDateLabel(date)}, ${dayMeetings.length} meeting${dayMeetings.length > 1 ? "s" : ""}`
                      : fullDateLabel(date)
                  }
                  aria-disabled={interactive ? undefined : "true"}
                  onClick={handleSelect}
                  onKeyDown={(e) => {
                    if (!interactive) return;
                    if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
                      e.preventDefault();
                      handleSelect();
                    }
                  }}
                  className={`${cellClasses} min-h-[72px] sm:min-h-[96px]`}
                >
                  <span
                    className={`self-end text-right text-[11px] font-heading font-bold leading-none ${
                      isToday
                        ? "inline-flex size-5 items-center justify-center self-start rounded-full bg-orange text-black"
                        : inMonth
                        ? "text-foreground"
                        : "text-muted-foreground"
                    }`}
                  >
                    {date.getDate()}
                  </span>

                  <div className="flex flex-col gap-0.5 min-w-0">
                    {visible.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectMeeting(m);
                        }}
                        title={`${formatChipTime(m.scheduled_time)} — ${m.title}`}
                        aria-label={`${fullDateLabel(date)}: ${m.title} at ${formatChipTime(m.scheduled_time)} (${m.status})`}
                        className={`w-full truncate text-left px-1 py-0.5 rounded border text-[10px] font-bold leading-tight transition-colors duration-150 motion-reduce:transition-none ${chipTone(m.status)}`}
                      >
                        {formatChipTime(m.scheduled_time)} · {m.title}
                      </button>
                    ))}
                    {hiddenCount > 0 && (
                      <span className="px-1 text-[10px] font-bold text-muted-foreground">+{hiddenCount} more</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
