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
          className="flex items-center gap-1 text-xs font-bold text-gray-400 hover:text-white transition-colors"
        >
          <ChevronLeft className="size-4" /> Back
        </button>
        <div className="flex items-center gap-2 pl-2 border-l-2 border-neutral-800">
          {avatarUrl ? (
            <img src={avatarUrl} alt={host.username} className="w-7 h-7 rounded-full border border-black object-cover" />
          ) : (
            <div className="w-7 h-7 rounded-full border border-black bg-[#97192c] flex items-center justify-center text-xs font-black text-white">
              {host.username[0]?.toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-sm font-black text-white">{host.username}</p>
            {host.title && <p className="text-[10px] text-[#ff7a1b] font-bold">{host.title}</p>}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Left: Calendar */}
        <div className="border-2 border-black bg-[#161412] rounded-base p-4 shadow-[2px_2px_0px_0px_#000]">
          {/* Duration */}
          <div className="flex items-center gap-2 mb-4">
            <Clock className="size-3.5 text-[#ff7a1b] shrink-0" />
            <div className="flex gap-1">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  className={`px-2 py-0.5 text-xs font-bold border border-black rounded transition-colors ${
                    duration === d ? "bg-[#ff7a1b] text-black" : "bg-[#222] text-gray-300 hover:bg-[#333]"
                  }`}
                >
                  {d}m
                </button>
              ))}
            </div>
          </div>

          {/* Month nav */}
          <div className="flex items-center justify-between mb-3">
            <button type="button" onClick={prevMonth} className="p-1 hover:text-[#ff7a1b] transition-colors">
              <ChevronLeft className="size-4" />
            </button>
            <span className="text-xs font-black text-white uppercase tracking-wider">
              {MONTHS[calMonth]} {calYear}
            </span>
            <button type="button" onClick={nextMonth} className="p-1 hover:text-[#ff7a1b] transition-colors">
              <ChevronRight className="size-4" />
            </button>
          </div>

          {/* Day-of-week headers */}
          <div className="grid grid-cols-7 mb-1">
            {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
              <div key={d} className="text-center text-[10px] font-black text-gray-600 uppercase py-1">{d}</div>
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
                      ? "bg-[#ff7a1b] text-black border border-black"
                      : isPast
                      ? "text-gray-700 cursor-not-allowed"
                      : isToday
                      ? "border border-[#ff7a1b] text-white hover:bg-[#ff7a1b] hover:text-black"
                      : "text-gray-300 hover:bg-neutral-800"
                  }`}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Slots or Booking Form */}
        <div className="border-2 border-black bg-[#161412] rounded-base p-4 shadow-[2px_2px_0px_0px_#000] min-h-[280px]">
          {step === "calendar" && (
            <>
              {!selectedDate && (
                <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm text-center space-y-2 pt-8">
                  <Calendar className="size-8 opacity-30" />
                  <p className="font-bold">Pick a date to see available slots</p>
                </div>
              )}
              {selectedDate && slotsLoading && (
                <div className="text-gray-400 text-xs font-bold pt-2">Loading slots…</div>
              )}
              {selectedDate && slotsError && (
                <div className="text-red-400 text-xs font-bold pt-2">{slotsError}</div>
              )}
              {selectedDate && !slotsLoading && !slotsError && (
                <div className="space-y-2">
                  <p className="text-xs font-black text-[#ff7a1b] uppercase tracking-wider">
                    {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
                  </p>
                  {slots.length === 0 ? (
                    <p className="text-xs text-gray-500 pt-2">No available slots for this day. Try another date.</p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                      {slots.map((slot) => (
                        <button
                          key={slot}
                          type="button"
                          onClick={() => handleSlotClick(slot)}
                          className="py-2 text-xs font-bold border-2 border-black bg-[#222] text-white hover:bg-[#ff7a1b] hover:text-black rounded transition-all"
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
              <div className="flex items-center gap-2 p-2 bg-[#ff7a1b]/10 border border-[#ff7a1b]/40 rounded text-xs text-[#ff7a1b] font-bold">
                <CheckCircle className="size-3.5 shrink-0" />
                {new Date(selectedSlot).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })} · {duration} min
                <button
                  type="button"
                  onClick={() => setStep("calendar")}
                  className="ml-auto text-gray-400 hover:text-white text-[10px] font-bold"
                >
                  Change
                </button>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Meeting Title</label>
                <input
                  type="text"
                  value={bookingTitle}
                  onChange={(e) => setBookingTitle(e.target.value)}
                  placeholder={`Sync with ${host.username}`}
                  className="w-full bg-[#222] border-2 border-black p-2 rounded text-xs text-white focus:outline-none focus:border-[#ff7a1b]"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Notes / Agenda</label>
                <textarea
                  value={bookingNotes}
                  onChange={(e) => setBookingNotes(e.target.value)}
                  placeholder="What do you want to discuss?"
                  rows={2}
                  className="w-full bg-[#222] border-2 border-black p-2 rounded text-xs text-white focus:outline-none focus:border-[#ff7a1b] resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Scope</label>
                <select
                  value={bookingScope}
                  onChange={(e) => setBookingScope(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2 rounded text-xs text-white focus:outline-none focus:border-[#ff7a1b]"
                >
                  <option value="invite">Invite Only</option>
                  <option value="open">Open (All contributors)</option>
                  <option value="hq">HQ Only</option>
                </select>
              </div>

              {submitError && (
                <div className="text-xs text-red-400 font-bold">{submitError}</div>
              )}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setStep("calendar")}
                  className="flex-1 py-2 text-xs font-bold border-2 border-black bg-neutral-800 text-white rounded hover:bg-neutral-700 transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2 text-xs font-bold border-2 border-black bg-[#ff7a1b] text-black rounded shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all disabled:opacity-50"
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
