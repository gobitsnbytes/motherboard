"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Globe2,
  Loader2,
  Video,
} from "lucide-react";

interface Pool {
  name: string;
  description: string | null;
  ready: boolean;
}
interface Slot {
  start: string;
  end: string;
}
interface Booking {
  uid: string;
  status: string;
  start: string;
  end: string;
  meeting_url: string | null;
  management_token: string;
}

const field =
  "mt-2 w-full min-w-0 rounded-base border-2 border-border bg-white px-3 py-3 font-heading text-sm text-dark outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2";
const action =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-base border-2 border-border bg-orange px-5 py-2.5 font-heading text-sm font-extrabold text-dark shadow-light transition-[transform,box-shadow] hover:translate-x-px hover:translate-y-px hover:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Something went wrong. Please try again.");
  }
  return response.json();
}

function localDate(value: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type: string) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function monthDays(month: string): Array<string | null> {
  const [year = 0, monthNumber = 1] = month.split("-").map(Number);
  const first = new Date(Date.UTC(year, monthNumber - 1, 1));
  const count = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  return [
    ...Array<string | null>(first.getUTCDay()).fill(null),
    ...Array.from(
      { length: count },
      (_, index) => `${month}-${String(index + 1).padStart(2, "0")}`,
    ),
  ];
}

function shiftMonth(month: string, offset: number): string {
  const [year = 0, monthNumber = 1] = month.split("-").map(Number);
  const next = new Date(Date.UTC(year, monthNumber - 1 + offset, 1));
  return next.toISOString().slice(0, 7);
}

function displayDay(date: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat("en-US", {
    ...options,
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
}

export default function PublicBookingPage() {
  const { poolSlug } = useParams<{ poolSlug: string }>();
  const [pool, setPool] = useState<Pool | null>(null);
  const [poolError, setPoolError] = useState<string | null>(null);
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [today, setToday] = useState("");
  const [month, setMonth] = useState("");
  const [date, setDate] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selected, setSelected] = useState<Slot | null>(null);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slotError, setSlotError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [bookingBusy, setBookingBusy] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const key = useRef<string | null>(null);
  const timesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const zone =
      Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata";
    const current = localDate(new Date(), zone);
    setTimezone(zone);
    setToday(current);
    setDate(current);
    setMonth(current.slice(0, 7));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    request<Pool>(`/api/calendar/public/${encodeURIComponent(poolSlug)}`, {
      signal: controller.signal,
    })
      .then(setPool)
      .catch((reason) => {
        if (!controller.signal.aborted)
          setPoolError(
            reason instanceof Error
              ? reason.message
              : "This booking page is unavailable.",
          );
      });
    return () => controller.abort();
  }, [poolSlug]);

  useEffect(() => {
    if (!date || !pool?.ready) {
      setSlots([]);
      return;
    }
    const controller = new AbortController();
    setLoadingSlots(true);
    setSlotError(null);
    setSlots([]);
    setSelected(null);
    key.current = null;
    try {
      // Include both UTC boundaries, then keep only slots on the chosen local day.
      const start = new Date(`${date}T00:00:00Z`);
      start.setUTCDate(start.getUTCDate() - 1);
      const end = new Date(`${date}T00:00:00Z`);
      end.setUTCDate(end.getUTCDate() + 2);
      const params = new URLSearchParams({
        start: start.toISOString(),
        end: end.toISOString(),
        time_zone: timezone,
      });
      request<Slot[]>(
        `/api/calendar/public/${encodeURIComponent(poolSlug)}/slots?${params}`,
        { signal: controller.signal },
      )
        .then((available) => {
          if (controller.signal.aborted) return;
          const now = Date.now();
          setSlots(
            available.filter(
              (slot) =>
                new Date(slot.start).getTime() > now &&
                localDate(new Date(slot.start), timezone) === date,
            ),
          );
        })
        .catch((reason) => {
          if (!controller.signal.aborted)
            setSlotError(
              reason instanceof Error
                ? reason.message
                : "Could not load times.",
            );
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoadingSlots(false);
        });
    } catch {
      setSlotError("Enter a valid time zone, such as Asia/Kolkata.");
      setLoadingSlots(false);
    }
    return () => controller.abort();
  }, [date, timezone, pool?.ready, poolSlug, retry]);

  function chooseDate(nextDate: string) {
    setDate(nextDate);
    setSelected(null);
    key.current = null;
    if (window.matchMedia("(max-width: 767px)").matches) {
      const behavior = window.matchMedia("(prefers-reduced-motion: reduce)")
        .matches
        ? "instant"
        : "smooth";
      requestAnimationFrame(() =>
        timesRef.current?.scrollIntoView({ behavior, block: "start" }),
      );
    }
  }

  function changeMonth(offset: number) {
    setMonth(shiftMonth(month, offset));
    setDate("");
    setSelected(null);
    key.current = null;
  }

  async function book(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    setBookingBusy(true);
    setBookingError(null);
    try {
      key.current ??= crypto.randomUUID();
      const result = await request<Booking>(
        `/api/calendar/public/${encodeURIComponent(poolSlug)}/book`,
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "Idempotency-Key": key.current,
          },
          body: JSON.stringify({
            start: selected.start,
            attendee_name: form.get("name"),
            attendee_email: form.get("email"),
            attendee_timezone: timezone,
            guest_emails: [],
          }),
        },
      );
      localStorage.setItem(
        `motherboard-booking-${result.uid}`,
        result.management_token,
      );
      setBooking(result);
    } catch (reason) {
      setBookingError(
        reason instanceof Error
          ? reason.message
          : "Booking failed. Please try again.",
      );
    } finally {
      setBookingBusy(false);
    }
  }

  const title = pool?.name || "Book a meeting";
  const summary = pool?.description?.split(
    "\n\nGOBITSNBYTES FOUNDATION · bits&bytes™",
  )[0];
  const selectedDate = date
    ? displayDay(date, { weekday: "long", month: "long", day: "numeric" })
    : "";
  const timezoneValid = (() => {
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: timezone });
      return true;
    } catch {
      return false;
    }
  })();
  const time = (slot: Slot) =>
    new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: timezone,
    }).format(new Date(slot.start));

  return (
    <main className="min-h-screen w-full overflow-x-hidden bg-[#f8f1e7] px-3 py-6 font-heading text-dark sm:px-6 sm:py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-5 flex items-center justify-between gap-3 px-1">
          <span className="text-lg font-black tracking-tight">
            bits&amp;bytes<span className="text-burgundy">™</span>
          </span>
          <span className="text-xs font-semibold text-[#57534e]">Meetings</span>
        </div>
        {poolError ? (
          <div
            role="alert"
            className="rounded-base border-2 border-red-700 bg-red-50 p-6 font-semibold text-red-950"
          >
            {poolError}
          </div>
        ) : !pool ? (
          <div
            className="h-[34rem] animate-pulse rounded-base border-2 border-border bg-white motion-reduce:animate-none"
            aria-label="Loading booking page"
          />
        ) : !pool.ready ? (
          <div
            role="status"
            className="rounded-base border-2 border-border bg-white p-8 shadow-light"
          >
            <CalendarDays
              className="mb-4 size-8 text-burgundy"
              aria-hidden="true"
            />
            <h1 className="text-2xl font-black">
              Booking is not available yet
            </h1>
            <p className="mt-2 max-w-xl leading-6 text-[#57534e]">
              This meeting link is still being set up. Please check back later
              or contact the person who shared it.
            </p>
          </div>
        ) : booking ? (
          <div className="mx-auto max-w-2xl rounded-base border-2 border-border bg-white p-7 shadow-light sm:p-10">
            <CheckCircle2
              className="mb-4 size-10 text-emerald-700"
              aria-hidden="true"
            />
            <h1 className="text-3xl font-black">You’re booked.</h1>
            <p className="mt-2 text-[#57534e]">
              {title} ·{" "}
              {new Intl.DateTimeFormat(undefined, {
                dateStyle: "full",
                timeStyle: "short",
                timeZone: timezone,
              }).format(new Date(booking.start))}
            </p>
            <p className="mt-5 leading-6">
              Your calendar invitation is on its way. It includes the Google
              Meet link and details for changing your booking.
            </p>
            {booking.meeting_url && (
              <a
                className={`${action} mt-6`}
                href={booking.meeting_url}
                target="_blank"
                rel="noreferrer"
              >
                Open Google Meet{" "}
                <ArrowRight className="size-4" aria-hidden="true" />
              </a>
            )}
          </div>
        ) : (
          <div className="overflow-hidden rounded-base border-2 border-border bg-white shadow-light">
            <div
              className={`grid min-w-0 ${selected ? "md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]" : "md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.25fr)_minmax(0,0.8fr)]"}`}
            >
              <aside className="min-w-0 border-b-2 border-border p-6 sm:p-8 md:border-b-0 md:border-r-2">
                <div className="mb-8 flex size-11 items-center justify-center rounded-base border-2 border-border bg-burgundy shadow-light">
                  <Image
                    src="/bitsnbytes-logo.png"
                    alt="bits&bytes logo"
                    width={36}
                    height={36}
                    className="size-9 object-contain"
                  />
                </div>
                <p className="text-sm font-bold text-burgundy">
                  bits&amp;bytes™
                </p>
                <h1 className="mt-2 break-words text-2xl font-black leading-tight tracking-tight sm:text-3xl">
                  {title}
                </h1>
                {summary && (
                  <p className="mt-3 text-sm leading-6 text-[#57534e]">
                    {summary}
                  </p>
                )}
                {selected && (
                  <div className="mt-7 flex gap-2 text-sm font-bold">
                    <CalendarDays
                      className="mt-0.5 size-4 shrink-0"
                      aria-hidden="true"
                    />
                    <span>
                      {selectedDate}
                      <br />
                      {time(selected)}
                    </span>
                  </div>
                )}
                <div className="mt-7 space-y-3 text-sm font-semibold text-[#57534e]">
                  <div className="flex items-center gap-2">
                    <Video className="size-4" aria-hidden="true" /> Google Meet
                  </div>
                  <div className="flex items-center gap-2">
                    <Globe2 className="size-4" aria-hidden="true" /> {timezone}
                  </div>
                </div>
                {!selected && (
                  <details className="mt-5 text-sm">
                    <summary className="cursor-pointer font-bold text-burgundy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange">
                      Change time zone
                    </summary>
                    <label className="mt-3 block font-bold">
                      Time zone
                      <input
                        className={field}
                        value={timezone}
                        onChange={(event) => setTimezone(event.target.value)}
                        placeholder="Asia/Kolkata"
                      />
                    </label>
                  </details>
                )}
              </aside>

              {selected ? (
                <section className="min-w-0 p-6 sm:p-8">
                  <button
                    type="button"
                    onClick={() => {
                      setSelected(null);
                      setBookingError(null);
                      key.current = null;
                    }}
                    className="mb-7 inline-flex min-h-11 items-center gap-2 text-sm font-bold text-burgundy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
                  >
                    <ArrowLeft className="size-4" aria-hidden="true" /> Back to
                    times
                  </button>
                  <h2 className="text-xl font-black">Your details</h2>
                  <p className="mt-1 text-sm text-[#57534e]">
                    We’ll email your invitation and Google Meet link.
                  </p>
                  <form onSubmit={book} className="mt-7 max-w-lg space-y-5">
                    <label className="block text-sm font-bold">
                      Your name
                      <input
                        className={field}
                        name="name"
                        required
                        maxLength={120}
                        autoComplete="name"
                      />
                    </label>
                    <label className="block text-sm font-bold">
                      Email address
                      <input
                        className={field}
                        name="email"
                        type="email"
                        required
                        autoComplete="email"
                      />
                    </label>
                    {bookingError && (
                      <p
                        role="alert"
                        className="text-sm font-bold text-red-800"
                      >
                        {bookingError}
                      </p>
                    )}
                    <button
                      className={`${action} w-full sm:w-auto`}
                      disabled={bookingBusy}
                    >
                      {bookingBusy ? (
                        <Loader2
                          className="size-4 animate-spin motion-reduce:animate-none"
                          aria-hidden="true"
                        />
                      ) : null}{" "}
                      Confirm booking{" "}
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </button>
                    <p className="text-xs leading-5 text-[#57534e]">
                      Cal.com sends the calendar invitation and meeting link.
                    </p>
                  </form>
                </section>
              ) : (
                <>
                  <section
                    className="min-w-0 border-b-2 border-border p-5 sm:p-8 md:border-b-0 md:border-r-2"
                    aria-label="Choose a date"
                  >
                    <div className="mb-6 flex items-center justify-between gap-2">
                      <h2 className="text-base font-black">
                        {month
                          ? displayDay(`${month}-01`, {
                              month: "long",
                              year: "numeric",
                            })
                          : "Calendar"}
                      </h2>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          aria-label="Previous month"
                          disabled={!today || month <= today.slice(0, 7)}
                          onClick={() => changeMonth(-1)}
                          className="flex size-10 items-center justify-center rounded-base hover:bg-[#f8f1e7] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange disabled:opacity-30"
                        >
                          <ChevronLeft className="size-5" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          aria-label="Next month"
                          disabled={!month}
                          onClick={() => changeMonth(1)}
                          className="flex size-10 items-center justify-center rounded-base hover:bg-[#f8f1e7] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
                        >
                          <ChevronRight className="size-5" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                    <div className="grid grid-cols-7 gap-1 text-center text-xs font-bold text-[#57534e]">
                      {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(
                        (day) => (
                          <span key={day} className="py-2">
                            {day}
                          </span>
                        ),
                      )}
                    </div>
                    <div className="grid grid-cols-7 gap-1">
                      {month
                        ? monthDays(month).map((day, index) =>
                            day ? (
                              <button
                                key={day}
                                type="button"
                                disabled={day < today}
                                onClick={() => chooseDate(day)}
                                aria-label={displayDay(day, {
                                  weekday: "long",
                                  month: "long",
                                  day: "numeric",
                                })}
                                aria-pressed={day === date}
                                className={`aspect-square min-h-10 rounded-base border-2 text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:border-transparent disabled:text-[#aaa39b] ${day === date ? "border-border bg-orange shadow-light" : "border-transparent hover:border-border hover:bg-[#f8f1e7]"}`}
                              >
                                {Number(day.slice(-2))}
                              </button>
                            ) : (
                              <span key={`blank-${index}`} />
                            ),
                          )
                        : null}
                    </div>
                    <p className="mt-7 text-xs leading-5 text-[#57534e]">
                      Select a day to see available times.
                    </p>
                  </section>

                  <section
                    ref={timesRef}
                    className="min-w-0 p-5 sm:p-8"
                    aria-label="Available times"
                    aria-live="polite"
                  >
                    <h2 className="mb-5 text-base font-black">
                      {selectedDate || "Available times"}
                    </h2>
                    {!timezoneValid ? (
                      <div role="alert" className="rounded-base border-2 border-red-700 bg-red-50 p-4 text-sm font-semibold text-red-950">
                        Enter a valid time zone, such as Asia/Kolkata.
                      </div>
                    ) : loadingSlots ? (
                      <div className="space-y-2" aria-label="Loading times">
                        {Array.from({ length: 5 }, (_, index) => (
                          <div
                            key={index}
                            className="h-11 animate-pulse rounded-base bg-[#eee8df] motion-reduce:animate-none"
                          />
                        ))}
                      </div>
                    ) : slotError ? (
                      <div className="rounded-base border-2 border-border bg-[#f8f1e7] p-4">
                        <p className="font-bold">Couldn’t load times</p>
                        <p className="mt-1 text-sm text-[#57534e]">
                          {slotError}
                        </p>
                        <button
                          type="button"
                          className="mt-3 text-sm font-bold text-burgundy underline underline-offset-4"
                          onClick={() => setRetry((value) => value + 1)}
                        >
                          Try again
                        </button>
                      </div>
                    ) : !date ? (
                      <div className="rounded-base border-2 border-dashed border-border bg-[#f8f1e7] p-5">
                        <CalendarDays
                          className="mb-3 size-6 text-burgundy"
                          aria-hidden="true"
                        />
                        <p className="font-bold">Choose a day</p>
                        <p className="mt-1 text-sm leading-6 text-[#57534e]">
                          Available times will appear here.
                        </p>
                      </div>
                    ) : slots.length === 0 ? (
                      <div className="rounded-base border-2 border-dashed border-border bg-[#f8f1e7] p-5">
                        <Clock3
                          className="mb-3 size-6 text-burgundy"
                          aria-hidden="true"
                        />
                        <p className="font-bold">
                          No times open{" "}
                          {date === today ? "today" : "on this day"}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-[#57534e]">
                          Choose another date on the calendar.
                        </p>
                      </div>
                    ) : (
                      <div className="max-h-[25rem] space-y-2 overflow-y-auto pr-1">
                        {slots.map((slot) => (
                          <button
                            key={slot.start}
                            type="button"
                            onClick={() => {
                              setSelected(slot);
                              key.current = null;
                            }}
                            className="flex min-h-11 w-full items-center justify-center rounded-base border-2 border-border bg-white px-3 py-2 font-bold transition-colors hover:bg-orange focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2"
                          >
                            {time(slot)}
                          </button>
                        ))}
                      </div>
                    )}
                  </section>
                </>
              )}
            </div>
          </div>
        )}
        <footer className="mt-6 space-y-1 text-center font-heading text-xs font-semibold text-[#57534e]">
          <p>GOBITSNBYTES FOUNDATION · bits&amp;bytes™</p>
          <p>
            © 2026 GOBITSNBYTES FOUNDATION. All rights reserved. | CIN:
            U85500UP2026NPL248652
          </p>
        </footer>
      </div>
    </main>
  );
}
