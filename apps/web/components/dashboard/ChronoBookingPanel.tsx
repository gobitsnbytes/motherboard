"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ChevronLeft, ChevronRight, Clock, Calendar, CheckCircle } from "lucide-react";

interface HostProfile {
  discord_id: string;
  username: string;
  email: string | null;
  timezone: string;
  weekly_hours: string | null;
  booking_link: string | null;
  title: string | null;
  description: string | null;
  calcom_event_type_id: string | null;
  associated_role_id: string | null;
  avatar: string | null;
}

interface ChronoBookingPanelProps {
  host: HostProfile;
  creatorDiscordId: string;
  creatorUsername: string;
  apiBase: string;
  onBooked: () => void;
  onBack: () => void;
}

const DURATIONS = [15, 30, 45, 60] as const;
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function formatDateYMD(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildCalendarDays(year: number, month: number): (Date | null)[] {
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const startPad = first.getDay(); // 0=Sun
  const days: (Date | null)[] = [];
  for (let i = 0; i < startPad; i++) days.push(null);
  for (let d = 1; d <= last.getDate(); d++) days.push(new Date(year, month, d));
  return days;
}

export default function ChronoBookingPanel({
  host,
  creatorDiscordId,
  creatorUsername,
  apiBase,
  onBooked,
  onBack,
}: ChronoBookingPanelProps) {
  const today = new Date();
  const [calYear, setCalYear] = useState(today.getFullYear());
  const [calMonth, setCalMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [duration, setDuration] = useState<number>(30);
  const [slots, setSlots] = useState<string[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  // Booking form
  const [step, setStep] = useState<"calendar" | "form">("calendar");
  const [bookingTitle, setBookingTitle] = useState("");
  const [bookingNotes, setBookingNotes] = useState("");
  const [bookingScope, setBookingScope] = useState("invite");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const avatarUrl = host.avatar
    ? `https://cdn.discordapp.com/avatars/${host.discord_id}/${host.avatar}.webp?size=128`
    : null;

  const fetchSlots = useCallback(
    async (date: string, dur: number) => {
      if (!host.booking_link) return;
      try {
        setSlotsLoading(true);
        setSlotsError(null);
        setSlots([]);
        setSelectedSlot(null);
        const res = await fetch(
          `${apiBase}/api/meetings/public/availability/${host.booking_link}/slots?date=${date}&duration=${dur}`
        );
        if (!res.ok) throw new Error("Could not load slots for this date");
        const data: string[] = await res.json();
        setSlots(data);
      } catch (err: unknown) {
        setSlotsError(err instanceof Error ? err.message : "Failed to load slots");
      } finally {
        setSlotsLoading(false);
      }
    },
    [apiBase, host.booking_link]
  );

  useEffect(() => {
    if (selectedDate) fetchSlots(selectedDate, duration);
  }, [selectedDate, duration, fetchSlots]);

  const handleDateClick = (d: Date) => {
    if (d < new Date(today.getFullYear(), today.getMonth(), today.getDate())) return;
    const ymd = formatDateYMD(d);
    setSelectedDate(ymd);
    setSelectedSlot(null);
    setStep("calendar");
  };

  const handleSlotClick = (slot: string) => {
    setSelectedSlot(slot);
    setStep("form");
  };

  const handleSubmitBooking = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDate || !selectedSlot || !host.booking_link) return;
    try {
      setSubmitting(true);
      setSubmitError(null);

      // Build scheduled_time from the slot (ISO string like "2026-08-10T09:00+05:30")
      const scheduledTimeMs = new Date(selectedSlot).getTime();

      const payload = {
        title: bookingTitle || `Sync with ${host.username}`,
        description: bookingNotes || null,
        scheduled_time: scheduledTimeMs,
        duration_minutes: duration,
        location_type: "discord_vc",
        location_details: null,
        creator_id: creatorDiscordId,
        invitees: [{ type: "user", id: host.discord_id }],
        external_emails: [],
        notes: bookingNotes || null,
        scope: bookingScope,
      };

      const res = await fetch("/api/meetings/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "Failed to book meeting");
      }

      onBooked();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to book meeting");
    } finally {
      setSubmitting(false);
    }
  };

  const calDays = buildCalendarDays(calYear, calMonth);
  const prevMonth = () => {
    if (calMonth === 0) { setCalMonth(11); setCalYear(y => y - 1); }
    else setCalMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (calMonth === 11) { setCalMonth(0); setCalYear(y => y + 1); }
    else setCalMonth(m => m + 1);
  };

  const formatSlot = (iso: string) => {
    return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  };

  return (
    <div className="space-y-4">
      {/* Back + host summary */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronLeft className="size-4" /> Back
        </button>
        <div className="flex items-center gap-2 pl-2 border-l-2 border-border">
          {avatarUrl ? (
            <img src={avatarUrl} alt={host.username} className="w-7 h-7 rounded-full border border-border object-cover" />
          ) : (
            <div className="w-7 h-7 rounded-full border border-border bg-burgundy flex items-center justify-center text-xs font-black text-white">
              {host.username[0]?.toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-sm font-black text-foreground">{host.username}</p>
            {host.title && <p className="text-[10px] text-orange font-bold">{host.title}</p>}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Left: Calendar */}
        <div className="border-2 border-border bg-secondary-background rounded-base p-4 shadow-shadow">
          {/* Duration */}
          <div className="flex items-center gap-2 mb-4">
            <Clock className="size-3.5 text-orange shrink-0" />
            <div className="flex gap-1">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  className={`px-2 py-0.5 text-xs font-bold border border-border rounded transition-colors ${
                    duration === d ? "bg-orange text-black" : "bg-muted text-muted-foreground hover:bg-background"
                  }`}
                >
                  {d}m
                </button>
              ))}
            </div>
          </div>

          {/* Month nav */}
          <div className="flex items-center justify-between mb-3">
            <button type="button" onClick={prevMonth} aria-label={`Previous month (${MONTHS[(calMonth + 11) % 12]} ${calMonth === 0 ? calYear - 1 : calYear})`} className="p-1 border-2 border-transparent rounded-base text-muted-foreground hover:text-orange hover:border-border transition-colors duration-150 motion-reduce:transition-none">
              <ChevronLeft className="size-4" />
            </button>
            <span className="text-xs font-black text-foreground uppercase tracking-wider">
              {MONTHS[calMonth]} {calYear}
            </span>
            <button type="button" onClick={nextMonth} aria-label={`Next month (${MONTHS[(calMonth + 1) % 12]} ${calMonth === 11 ? calYear + 1 : calYear})`} className="p-1 border-2 border-transparent rounded-base text-muted-foreground hover:text-orange hover:border-border transition-colors duration-150 motion-reduce:transition-none">
              <ChevronRight className="size-4" />
            </button>
          </div>

          {/* Day-of-week headers */}
          <div className="grid grid-cols-7 mb-1">
            {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
              <div key={d} className="text-center text-[10px] font-black text-muted-foreground uppercase py-1">{d}</div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-0.5">
            {calDays.map((d, i) => {
              if (!d) return <div key={`pad-${i}`} />;
              const ymd = formatDateYMD(d);
              const isPast = d < new Date(today.getFullYear(), today.getMonth(), today.getDate());
              const isSelected = selectedDate === ymd;
              const isToday = ymd === formatDateYMD(today);
              return (
                <button
                  key={ymd}
                  type="button"
                  onClick={() => handleDateClick(d)}
                  disabled={isPast}
                  className={`text-xs py-1.5 rounded font-bold transition-all ${
                    isSelected
                      ? "bg-orange text-black border border-border"
                      : isPast
                      ? "text-muted-foreground/50 cursor-not-allowed"
                      : isToday
                      ? "border border-orange text-foreground hover:bg-orange hover:text-black"
                      : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Slots or Booking Form */}
        <div className="border-2 border-border bg-secondary-background rounded-base p-4 shadow-shadow min-h-[280px]">
          {step === "calendar" && (
            <>
              {!selectedDate && (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm text-center space-y-2 pt-8">
                  <Calendar className="size-8 opacity-30" />
                  <p className="font-bold">Pick a date to see available slots</p>
                </div>
              )}
              {selectedDate && slotsLoading && (
                <div className="text-muted-foreground text-xs font-bold pt-2">Loading slots…</div>
              )}
              {selectedDate && slotsError && (
                <div className="text-red-700 text-xs font-bold pt-2">{slotsError}</div>
              )}
              {selectedDate && !slotsLoading && !slotsError && (
                <div className="space-y-2">
                  <p className="text-xs font-black text-orange uppercase tracking-wider">
                    {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
                  </p>
                  {slots.length === 0 ? (
                    <p className="text-xs text-muted-foreground pt-2">No available slots for this day. Try another date.</p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                      {slots.map((slot) => (
                        <button
                          key={slot}
                          type="button"
                          onClick={() => handleSlotClick(slot)}
                          className="py-2 text-xs font-bold border-2 border-border bg-muted text-foreground hover:bg-orange hover:text-black rounded transition-all"
                        >
                          {formatSlot(slot)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {step === "form" && selectedSlot && (
            <form onSubmit={handleSubmitBooking} className="space-y-3">
              <div className="flex items-center gap-2 p-2 bg-orange/10 border border-orange/40 rounded text-xs text-orange font-bold">
                <CheckCircle className="size-3.5 shrink-0" />
                {new Date(selectedSlot).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })} · {duration} min
                <button
                  type="button"
                  onClick={() => setStep("calendar")}
                  className="ml-auto text-muted-foreground hover:text-foreground text-[10px] font-bold"
                >
                  Change
                </button>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Meeting Title</label>
                <input
                  type="text"
                  value={bookingTitle}
                  onChange={(e) => setBookingTitle(e.target.value)}
                  placeholder={`Sync with ${host.username}`}
                  className="w-full bg-background border-2 border-border p-2 rounded text-xs text-foreground focus:outline-none focus:border-orange"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Notes / Agenda</label>
                <textarea
                  value={bookingNotes}
                  onChange={(e) => setBookingNotes(e.target.value)}
                  placeholder="What do you want to discuss?"
                  rows={2}
                  className="w-full bg-background border-2 border-border p-2 rounded text-xs text-foreground focus:outline-none focus:border-orange resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Scope</label>
                <select
                  value={bookingScope}
                  onChange={(e) => setBookingScope(e.target.value)}
                  className="w-full bg-background border-2 border-border p-2 rounded text-xs text-foreground focus:outline-none focus:border-orange"
                >
                  <option value="invite">Invite Only</option>
                  <option value="open">Open (All contributors)</option>
                  <option value="hq">HQ Only</option>
                </select>
              </div>

              {submitError && (
                <div className="text-xs text-red-700 font-bold">{submitError}</div>
              )}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setStep("calendar")}
                  className="flex-1 py-2 text-xs font-bold border-2 border-border bg-muted text-foreground rounded hover:bg-background transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2 text-xs font-bold border-2 border-border bg-orange text-black rounded shadow-shadow hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all disabled:opacity-50"
                >
                  {submitting ? "Booking…" : "Confirm Booking"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
