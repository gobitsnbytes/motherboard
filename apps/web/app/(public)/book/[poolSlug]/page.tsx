"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { CalendarDays, CheckCircle2, Clock, Loader2, Video } from "lucide-react";

interface Slot { start: string; end: string; }
interface Booking { uid: string; status: string; start: string; end: string; meeting_url: string | null; management_token: string; }

const field = "w-full rounded-base border-2 border-border bg-secondary-background px-3 py-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-orange focus:ring-2 focus:ring-orange/25";
const button = "inline-flex min-h-11 items-center justify-center gap-2 rounded-base border-2 border-border bg-orange px-5 py-2.5 text-sm font-black text-black shadow-light transition-[transform,box-shadow] hover:translate-x-px hover:translate-y-px hover:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange disabled:cursor-not-allowed disabled:opacity-50";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Request failed. Please try again.");
  }
  return response.json();
}

export default function PublicBookingPage() {
  const { poolSlug } = useParams<{ poolSlug: string }>();
  const [date, setDate] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selected, setSelected] = useState<Slot | null>(null);
  const [loading, setLoading] = useState(false);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null);

  useEffect(() => {
    try { setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata"); } catch { /* use default */ }
  }, []);

  async function findSlots(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null); setSelected(null);
    try {
      const start = `${date}T00:00:00Z`;
      const end = `${date}T23:59:59Z`;
      setSlots(await request<Slot[]>(`/api/calendar/public/${encodeURIComponent(poolSlug)}/slots?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&time_zone=${encodeURIComponent(timezone)}`));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load availability"); }
    finally { setLoading(false); }
  }

  async function book(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return;
    const form = new FormData(event.currentTarget); setLoading(true); setError(null);
    try {
      key.current ??= crypto.randomUUID();
      const result = await request<Booking>(`/api/calendar/public/${encodeURIComponent(poolSlug)}/book`, {
        method: "POST",
        headers: { "content-type": "application/json", "Idempotency-Key": key.current },
        body: JSON.stringify({ start: selected.start, attendee_name: form.get("name"), attendee_email: form.get("email"), attendee_timezone: timezone, guest_emails: [] }),
      });
      localStorage.setItem(`motherboard-booking-${result.uid}`, result.management_token);
      setBooking(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Booking failed"); }
    finally { setLoading(false); }
  }

  const minDate = new Date().toISOString().slice(0, 10);
  return <main className="min-h-screen bg-background px-4 py-10 text-foreground sm:py-16">
    <div className="mx-auto max-w-4xl">
      <header className="mb-8 border-b-2 border-border pb-6"><div className="mb-3 inline-flex items-center gap-2 text-sm font-bold text-orange"><Video className="size-4" /> Google Meet via Cal.com</div><h1 className="text-3xl font-black tracking-tight sm:text-4xl">Book a time with bits&amp;bytes</h1><p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">Pick one shared time. Motherboard finds an available host; Cal.com sends the confirmation and creates the Google Meet.</p></header>

      {error && <div role="alert" className="mb-5 rounded-base border-2 border-red-700 bg-red-100 p-3 text-sm font-semibold text-red-950">{error}</div>}
      {booking ? <section className="rounded-base border-2 border-emerald-800 bg-emerald-50 p-6 text-emerald-950"><CheckCircle2 className="mb-3 size-8" /><h2 className="text-2xl font-black">You’re booked.</h2><p className="mt-2">{new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeStyle: "short" }).format(new Date(booking.start))}</p><p className="mt-1 text-sm">Cal.com has sent the calendar invitation. Keep that email for rescheduling or cancellation.</p>{booking.meeting_url && <a className={`${button} mt-5`} href={booking.meeting_url} target="_blank" rel="noreferrer">Open Google Meet</a>}</section> : <div className="grid gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <form onSubmit={findSlots} className="h-fit space-y-4 rounded-base border-2 border-border bg-secondary-background p-5"><div><h2 className="font-black">Choose a day</h2><p className="mt-1 text-sm text-muted-foreground">Availability comes directly from each host’s connected calendars.</p></div><label className="block text-sm font-bold">Date<input className={`${field} mt-1`} type="date" min={minDate} required value={date} onChange={(event) => setDate(event.target.value)} /></label><label className="block text-sm font-bold">Time zone<input className={`${field} mt-1`} required value={timezone} onChange={(event) => setTimezone(event.target.value)} /></label><button className={`${button} w-full`} disabled={loading}>{loading ? <Loader2 className="size-4 animate-spin motion-reduce:animate-none" /> : <CalendarDays className="size-4" />} Show times</button></form>
        <section aria-labelledby="times-title"><h2 id="times-title" className="text-xl font-black">Available times</h2><p className="mb-4 mt-1 text-sm text-muted-foreground">Times are displayed in {timezone}.</p>{slots.length === 0 ? <div className="rounded-base border-2 border-dashed border-border p-8 text-center text-sm text-muted-foreground">Choose a date to see availability.</div> : <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{slots.map((slot) => <button key={slot.start} type="button" onClick={() => setSelected(slot)} className={`min-h-11 rounded-base border-2 px-3 py-2 text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ${selected?.start === slot.start ? "border-black bg-orange text-black shadow-light" : "border-border bg-secondary-background hover:bg-muted"}`}><Clock className="mr-1.5 inline size-4" />{new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", timeZone: timezone }).format(new Date(slot.start))}</button>)}</div>}
          {selected && <form onSubmit={book} className="mt-6 space-y-4 border-t-2 border-border pt-5"><h3 className="font-black">Your details</h3><label className="block text-sm font-bold">Name<input className={`${field} mt-1`} name="name" required maxLength={120} autoComplete="name" /></label><label className="block text-sm font-bold">Email<input className={`${field} mt-1`} name="email" type="email" required autoComplete="email" /></label><button className={`${button} w-full`} disabled={loading}>{loading ? <Loader2 className="size-4 animate-spin motion-reduce:animate-none" /> : <Video className="size-4" />} Confirm with Cal.com</button><p className="text-xs leading-5 text-muted-foreground">One submission creates one booking. Cal.com sends all invitations and updates; Motherboard sends no duplicate email.</p></form>}
        </section>
      </div>}
    </div>
  </main>;
}
