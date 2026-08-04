"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Users,
  FileText,
  AlertTriangle,
  Plus,
  Save,
  CheckCircle,
  Search,
  Zap,
  ExternalLink,
  RefreshCw,
  CalendarClock,
  Bell,
  X,
} from "lucide-react";
import AvailabilityGrid from "../../../components/dashboard/AvailabilityGrid";
import ChronoHostGrid from "../../../components/dashboard/ChronoHostGrid";
import ChronoBookingPanel from "../../../components/dashboard/ChronoBookingPanel";

// ─── Types ──────────────────────────────────────────────────────────────────

interface MeetingAttendee {
  meeting_id: string;
  attendee_type: string;
  discord_id: string;
}

interface MeetingTranscript {
  meeting_id: string;
  summary: string | null;
  key_decisions: string | null;
  action_items: string | null;
  full_transcript: string | null;
  timestamped_transcript: string | null;
  vc_text_messages: string | null;
  audio_duration_seconds: number | null;
  speaker_count: number | null;
  processed_at: string | null;
}

interface Meeting {
  id: string;
  title: string;
  description: string | null;
  scheduled_time: number;
  location_type: string;
  location_details: string | null;
  temp_channel_id: string | null;
  status: string;
  creator_id: string;
  created_at: number;
  calcom_booking_id: string | null;
  end_time: number | null;
  external_emails: string | null;
  recording_status: string;
  meet_code: string | null;
  booked_by: string | null;
  scope: string;
  activated_at: number | null;
  attendees: MeetingAttendee[];
  transcript?: MeetingTranscript | null;
}

interface UserAvailability {
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

interface MeetingEmailPreference {
  discord_id: string;
  email: string;
  notify_on_invite: number;
  notify_on_reminder: number;
}

type ActiveTab = "meetings" | "book" | "availability" | "notifications";

// ─── Constants ───────────────────────────────────────────────────────────────

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : "");

const TIMEZONES = [
  "Asia/Kolkata",
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Singapore",
  "Australia/Sydney",
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getStatusColor(status: string) {
  switch (status) {
    case "scheduled": return "bg-cyan-200 text-cyan-900 border-cyan-800";
    case "active": return "bg-green-200 text-green-900 border-green-800 animate-pulse";
    case "completed": return "bg-gray-200 text-gray-900 border-gray-800";
    case "cancelled": return "bg-red-200 text-red-900 border-red-800";
    default: return "bg-white text-black border-black";
  }
}

function formatTime(epoch: number) {
  return new Date(epoch).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

function parseActionItems(raw: string | null): { assignee?: string; task?: string; deadline?: string }[] {
  try { return JSON.parse(raw || "[]"); } catch { return []; }
}

function parseStringArray(raw: string | null): string[] {
  try { return JSON.parse(raw || "[]"); } catch { return []; }
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 font-bold border-2 border-black rounded-t-base transition-all text-sm whitespace-nowrap ${
        active
          ? "bg-[#ff7a1b] text-black shadow-[2px_2px_0px_0px_#000] translate-y-[-2px]"
          : "bg-[#222] text-white hover:bg-[#2a2a2a]"
      }`}
    >
      {label}
    </button>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function MeetingsPage() {
  const { data: session } = useSession();
  const discordId = session?.user?.discordId ?? "";
  const username = session?.user?.name ?? "User";
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<ActiveTab>("meetings");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showRescheduleModal, setShowRescheduleModal] = useState<Meeting | null>(null);

  // ⚡ Instant Meet
  const [instantTitle, setInstantTitle] = useState("");
  const [instantScope, setInstantScope] = useState("open");
  const [instantLoading, setInstantLoading] = useState(false);
  const [instantResult, setInstantResult] = useState<{ meet_code: string; id: string } | null>(null);

  // Schedule form
  const [scheduleTitle, setScheduleTitle] = useState("");
  const [scheduleDesc, setScheduleDesc] = useState("");
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [scheduleDuration, setScheduleDuration] = useState("30");
  const [scheduleLocationType, setScheduleLocationType] = useState("discord_vc");
  const [scheduleLocationDetails, setScheduleLocationDetails] = useState("");
  const [scheduleScope, setScheduleScope] = useState("invite");
  const [scheduleInvitees, setScheduleInvitees] = useState("");
  const [scheduleEmails, setScheduleEmails] = useState("");
  const [scheduleNotes, setScheduleNotes] = useState("");
  const [scheduleLoading, setScheduleLoading] = useState(false);

  // Availability form
  const [availEmail, setAvailEmail] = useState("");
  const [availTimezone, setAvailTimezone] = useState("Asia/Kolkata");
  const [availWeeklyHours, setAvailWeeklyHours] = useState<string | null>(null);
  const [availBookingLink, setAvailBookingLink] = useState("");
  const [availTitle, setAvailTitle] = useState("");
  const [availDescription, setAvailDescription] = useState("");
  const [availCalcomId, setAvailCalcomId] = useState("");
  const [availLoading, setAvailLoading] = useState(false);
  const [availSuccess, setAvailSuccess] = useState(false);

  // Notification prefs
  const [prefEmail, setPrefEmail] = useState("");
  const [prefNotifyInvite, setPrefNotifyInvite] = useState(true);
  const [prefNotifyReminder, setPrefNotifyReminder] = useState(true);
  const [prefLoading, setPrefLoading] = useState(false);
  const [prefSuccess, setPrefSuccess] = useState(false);

  // Reschedule form
  const [reschedDate, setReschedDate] = useState("");
  const [reschedTime, setReschedTime] = useState("");
  const [reschedReason, setReschedReason] = useState("");
  const [reschedLoading, setReschedLoading] = useState(false);

  // Transcript filter
  const [transcriptSearch, setTranscriptSearch] = useState("");

  // Book a Sync tab
  const [selectedHost, setSelectedHost] = useState<HostProfile | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState(false);

  // ─── Data fetching ─────────────────────────────────────────────────────────

  const fetchMeetings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/meetings");
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) throw new Error("Failed to load meetings");
      setMeetings(await res.json());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load meetings");
    } finally {
      setLoading(false);
    }
  }, [router]);

  const fetchAvailability = useCallback(async () => {
    if (!discordId) return;
    try {
      const res = await fetch(`/api/meetings/availability/${discordId}`);
      if (res.ok) {
        const data: UserAvailability = await res.json();
        setAvailEmail(data.email ?? "");
        setAvailTimezone(data.timezone ?? "Asia/Kolkata");
        setAvailWeeklyHours(data.weekly_hours ?? null);
        setAvailBookingLink(data.booking_link ?? "");
        setAvailTitle(data.title ?? "");
        setAvailDescription(data.description ?? "");
        setAvailCalcomId(data.calcom_event_type_id ?? "");
      }
    } catch { /* silent */ }
  }, [discordId]);

  const fetchPreferences = useCallback(async () => {
    if (!discordId) return;
    try {
      const res = await fetch(`/api/meetings/preferences/${discordId}`);
      if (res.ok) {
        const data: MeetingEmailPreference = await res.json();
        setPrefEmail(data.email ?? "");
        setPrefNotifyInvite(data.notify_on_invite === 1);
        setPrefNotifyReminder(data.notify_on_reminder === 1);
      }
    } catch { /* silent */ }
  }, [discordId]);

  useEffect(() => {
    fetchMeetings();
    fetchAvailability();
    fetchPreferences();
  }, [fetchMeetings, fetchAvailability, fetchPreferences]);

  // ─── Handlers ──────────────────────────────────────────────────────────────

  const handleInstantMeet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!discordId || !instantTitle.trim()) return;
    try {
      setInstantLoading(true);
      setInstantResult(null);
      const payload = {
        title: instantTitle.trim(),
        description: "Instant meeting",
        scheduled_time: Date.now(),
        duration_minutes: 60,
        location_type: "discord_vc",
        location_details: null,
        creator_id: discordId,
        invitees: [],
        external_emails: [],
        notes: null,
        scope: instantScope,
      };
      const res = await fetch("/api/meetings/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const b = await res.json(); throw new Error(b.detail ?? "Failed to create meeting"); }
      const data: Meeting = await res.json();
      setInstantResult({ meet_code: data.meet_code ?? "", id: data.id });
      fetchMeetings();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to create instant meeting");
    } finally {
      setInstantLoading(false);
    }
  };

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!discordId) return;
    try {
      setScheduleLoading(true);
      const scheduledTimeMs = new Date(`${scheduleDate}T${scheduleTime}:00`).getTime();
      if (isNaN(scheduledTimeMs)) throw new Error("Invalid date or time");

      const invitees = scheduleInvitees
        .split(",").map((s) => s.trim()).filter(Boolean)
        .map((id) => ({ type: id.length > 15 ? "role" : "user", id }));

      const externalEmails = scheduleEmails
        .split(",").map((e) => e.trim()).filter((e) => e.includes("@"));

      const res = await fetch("/api/meetings/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: scheduleTitle,
          description: scheduleDesc || null,
          scheduled_time: scheduledTimeMs,
          duration_minutes: parseInt(scheduleDuration, 10),
          location_type: scheduleLocationType,
          location_details: scheduleLocationDetails || null,
          creator_id: discordId,
          invitees,
          external_emails: externalEmails,
          notes: scheduleNotes || null,
          scope: scheduleScope,
        }),
      });
      if (!res.ok) { const b = await res.json(); throw new Error(b.detail ?? "Failed to schedule meeting"); }
      setShowScheduleModal(false);
      setScheduleTitle(""); setScheduleDesc(""); setScheduleDate(""); setScheduleTime("");
      setScheduleLocationDetails(""); setScheduleInvitees(""); setScheduleEmails(""); setScheduleNotes("");
      fetchMeetings();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to schedule meeting");
    } finally {
      setScheduleLoading(false);
    }
  };

  const handleSaveAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!discordId) return;
    try {
      setAvailLoading(true);
      setAvailSuccess(false);
      const res = await fetch("/api/meetings/availability", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          discord_id: discordId,
          username,
          email: availEmail || null,
          timezone: availTimezone,
          weekly_hours: availWeeklyHours,
          booking_link: availBookingLink || null,
          title: availTitle || null,
          description: availDescription || null,
          calcom_event_type_id: availCalcomId || null,
          associated_role_id: null,
          avatar: null,
        }),
      });
      if (!res.ok) throw new Error("Failed to save availability");
      setAvailSuccess(true);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to save availability");
    } finally {
      setAvailLoading(false);
    }
  };

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!discordId) return;
    try {
      setPrefLoading(true);
      setPrefSuccess(false);
      const res = await fetch("/api/meetings/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          discord_id: discordId,
          email: prefEmail,
          notify_on_invite: prefNotifyInvite ? 1 : 0,
          notify_on_reminder: prefNotifyReminder ? 1 : 0,
          updated_at: Date.now(),
        }),
      });
      if (!res.ok) throw new Error("Failed to save preferences");
      setPrefSuccess(true);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setPrefLoading(false);
    }
  };

  const handleCancelMeeting = async (meetingId: string) => {
    if (!confirm("Cancel this meeting? All attendees will be notified.")) return;
    try {
      const res = await fetch(`/api/meetings/${meetingId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to cancel meeting");
      setSelectedMeeting(null);
      fetchMeetings();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to cancel meeting");
    }
  };

  const handleReschedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showRescheduleModal) return;
    try {
      setReschedLoading(true);
      const newTime = new Date(`${reschedDate}T${reschedTime}:00`).getTime();
      if (isNaN(newTime)) throw new Error("Invalid date or time");
      const res = await fetch(`/api/meetings/${showRescheduleModal.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_time: newTime, notes: reschedReason || null }),
      });
      if (!res.ok) { const b = await res.json(); throw new Error(b.detail ?? "Failed to reschedule"); }
      setShowRescheduleModal(null);
      setReschedDate(""); setReschedTime(""); setReschedReason("");
      fetchMeetings();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to reschedule meeting");
    } finally {
      setReschedLoading(false);
    }
  };

  const handleBookingSuccess = useCallback(() => {
    setBookingSuccess(true);
    setSelectedHost(null);
    fetchMeetings();
    setTimeout(() => setBookingSuccess(false), 4000);
  }, [fetchMeetings]);

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 max-w-6xl mx-auto p-4">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-heading font-black tracking-tight text-white flex items-center gap-3">
            MEETINGS
            <span className="text-sm font-black text-[#ff7a1b] border-2 border-[#ff7a1b] px-2 py-0.5 rounded">
              chrono
            </span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Schedule, book, and manage calls — all in one place.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowScheduleModal(true); }}
            className="flex items-center gap-2 px-4 py-2.5 font-bold border-2 border-black bg-main text-main-foreground shadow-[4px_4px_0px_0px_#000] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000] transition-all rounded-base text-sm"
          >
            <Plus className="size-4 shrink-0" />
            Schedule
          </button>
        </div>
      </div>

      {/* ⚡ Instant Meet Banner */}
      <div className="border-2 border-black bg-[#1a1200] rounded-base p-4 shadow-[4px_4px_0px_0px_#000]">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="size-4 text-[#ff7a1b] shrink-0" />
          <span className="text-sm font-black text-white uppercase tracking-wider">⚡ Instant Meeting</span>
          <span className="text-xs text-gray-500">— launch a live VC right now</span>
        </div>
        {instantResult ? (
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 p-3 bg-green-950 border-2 border-green-800 rounded-base">
            <CheckCircle className="size-5 text-green-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-green-200">Meeting created!</p>
              <p className="text-xs text-green-400 font-mono mt-0.5">
                cal.gobitsnbytes.org/m/{instantResult.meet_code}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(`https://cal.gobitsnbytes.org/m/${instantResult.meet_code}`)}
                className="text-xs font-bold px-3 py-1.5 border-2 border-green-700 text-green-300 rounded hover:bg-green-900 transition-colors"
              >
                Copy Link
              </button>
              <button
                type="button"
                onClick={() => setInstantResult(null)}
                className="text-xs font-bold px-3 py-1.5 border-2 border-black bg-neutral-800 text-white rounded hover:bg-neutral-700 transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleInstantMeet} className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              required
              value={instantTitle}
              onChange={(e) => setInstantTitle(e.target.value)}
              placeholder="Meeting title (e.g. Quick sync, Sprint review…)"
              className="flex-1 bg-[#222] border-2 border-black p-2 rounded-base text-sm text-white focus:outline-none focus:border-[#ff7a1b]"
            />
            <select
              value={instantScope}
              onChange={(e) => setInstantScope(e.target.value)}
              className="bg-[#222] border-2 border-black p-2 rounded-base text-sm text-white focus:outline-none focus:border-[#ff7a1b] w-44 shrink-0"
            >
              <option value="open">Open (All contributors)</option>
              <option value="invite">Invite Only</option>
              <option value="hq">HQ Only</option>
              <option value="tech">Tech Council</option>
              <option value="creative">Creative Council</option>
              <option value="ops">Ops Council</option>
            </select>
            <button
              type="submit"
              disabled={instantLoading}
              className="flex items-center gap-2 px-4 py-2 font-bold border-2 border-black bg-[#ff7a1b] text-black shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all rounded-base text-sm shrink-0 disabled:opacity-50"
            >
              <Zap className="size-4 shrink-0" />
              {instantLoading ? "Launching…" : "Start Now"}
            </button>
          </form>
        )}
      </div>

      {/* Booking success banner */}
      {bookingSuccess && (
        <div className="flex items-center gap-3 p-3 bg-green-950 border-2 border-green-800 rounded-base text-green-200 text-sm font-bold">
          <CheckCircle className="size-5 shrink-0 text-green-400" />
          Booking confirmed! The meeting has been scheduled and invites sent.
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b-4 border-black pb-2 overflow-x-auto">
        <TabButton label="My Meetings" active={activeTab === "meetings"} onClick={() => setActiveTab("meetings")} />
        <TabButton label="Book a Sync" active={activeTab === "book"} onClick={() => setActiveTab("book")} />
        <TabButton label="My Availability" active={activeTab === "availability"} onClick={() => setActiveTab("availability")} />
        <TabButton label="Notifications" active={activeTab === "notifications"} onClick={() => setActiveTab("notifications")} />
      </div>

      {/* ── Tab: My Meetings ─────────────────────────────────────────────── */}
      {activeTab === "meetings" && (
        <div className="space-y-4">
          {loading ? (
            <div className="border-4 border-black bg-neutral-900 p-8 text-center text-white font-bold rounded-base shadow-[4px_4px_0px_0px_#000]">
              Loading meetings…
            </div>
          ) : error ? (
            <div className="border-4 border-black bg-red-950 text-red-200 p-4 font-bold rounded-base flex items-center gap-3">
              <AlertTriangle className="size-6 shrink-0" />
              <span>{error}</span>
              <button onClick={fetchMeetings} className="ml-auto text-xs underline">Retry</button>
            </div>
          ) : meetings.length === 0 ? (
            <div className="border-4 border-black bg-neutral-900 p-8 text-center rounded-base shadow-[4px_4px_0px_0px_#000]">
              <CalendarClock className="size-10 mx-auto mb-3 text-gray-600" />
              <p className="text-gray-400 font-bold">No meetings yet.</p>
              <p className="text-xs text-gray-600 mt-1">Use ⚡ Instant Meet, Schedule, or Book a Sync above.</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {meetings.map((meeting) => (
                <div
                  key={meeting.id}
                  onClick={() => setSelectedMeeting(meeting)}
                  className="border-4 border-black bg-[#161412] hover:bg-[#1a1816] p-5 rounded-base shadow-[4px_4px_0px_0px_#000] cursor-pointer transition-all hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_#000] flex flex-col justify-between"
                >
                  <div>
                    <div className="flex justify-between items-start gap-2">
                      <h2 className="text-lg font-heading font-black text-white line-clamp-1">{meeting.title}</h2>
                      <span className={`text-xs font-black uppercase px-2.5 py-1 border-2 border-black rounded-full shrink-0 ${getStatusColor(meeting.status)}`}>
                        {meeting.status}
                      </span>
                    </div>
                    {meeting.description && (
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{meeting.description}</p>
                    )}
                    <div className="mt-3 space-y-1.5">
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <Clock className="size-3.5 text-[#ff7a1b] shrink-0" />
                        <span>{formatTime(meeting.scheduled_time)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <MapPin className="size-3.5 text-[#ff7a1b] shrink-0" />
                        <span>{meeting.location_type === "discord_vc" ? "Discord Voice Channel" : meeting.location_details || "External"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <Users className="size-3.5 text-[#ff7a1b] shrink-0" />
                        <span>{meeting.attendees?.length || 1} attendee(s)</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t-2 border-neutral-800 flex justify-between items-center gap-2">
                    <span className="text-xs text-gray-600 font-mono truncate">
                      {meeting.meet_code ?? "No code"}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                      {meeting.status === "active" && meeting.temp_channel_id && (
                        <a
                          href={`discord://discordapp.com/channels/${meeting.temp_channel_id}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs font-black px-2 py-0.5 bg-green-400 text-black border border-black rounded hover:bg-green-300 transition-colors"
                        >
                          Join VC
                        </a>
                      )}
                      {meeting.meet_code && (
                        <a
                          href={`https://cal.gobitsnbytes.org/m/${meeting.meet_code}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-gray-500 hover:text-[#ff7a1b] transition-colors"
                          title="Open meeting page"
                        >
                          <ExternalLink className="size-3.5" />
                        </a>
                      )}
                      {meeting.status === "completed" && (
                        <span className="flex items-center gap-1 text-xs font-bold text-green-400">
                          <FileText className="size-3.5 shrink-0" />
                          AI Brief
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Book a Sync ─────────────────────────────────────────────── */}
      {activeTab === "book" && (
        <div className="space-y-4">
          {selectedHost ? (
            <ChronoBookingPanel
              host={selectedHost}
              creatorDiscordId={discordId}
              creatorUsername={username}
              apiBase={API_BASE}
              onBooked={handleBookingSuccess}
              onBack={() => setSelectedHost(null)}
            />
          ) : (
            <>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-heading font-black text-white">BOOK A SYNC</h2>
                <a
                  href="https://cal.gobitsnbytes.org"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-gray-500 hover:text-[#ff7a1b] transition-colors"
                >
                  <ExternalLink className="size-3" />
                  Public portal
                </a>
              </div>
              <ChronoHostGrid
                onSelectHost={setSelectedHost}
                selectedHostLink={selectedHost ? (selectedHost as HostProfile).booking_link : null}
                apiBase={API_BASE}
              />
            </>
          )}
        </div>
      )}

      {/* ── Tab: My Availability ─────────────────────────────────────────── */}
      {activeTab === "availability" && (
        <form onSubmit={handleSaveAvailability} className="space-y-5 max-w-2xl">
          <div>
            <h2 className="text-2xl font-heading font-black text-white">MY AVAILABILITY</h2>
            <p className="text-xs text-gray-400 mt-1">
              This powers your public booking page at{" "}
              <a
                href={availBookingLink ? `https://cal.gobitsnbytes.org/${availBookingLink}` : "https://cal.gobitsnbytes.org"}
                target="_blank"
                rel="noreferrer"
                className="text-[#ff7a1b] hover:underline"
              >
                cal.gobitsnbytes.org/{availBookingLink || "…"}
              </a>
            </p>
          </div>

          {availSuccess && (
            <div className="bg-green-950 text-green-200 border-2 border-green-800 p-3 rounded-base font-bold text-sm flex items-center gap-2">
              <CheckCircle className="size-4 shrink-0" />
              Availability saved! Your booking page is now live.
            </div>
          )}

          <div className="border-2 border-black bg-[#161412] rounded-base p-4 shadow-[2px_2px_0px_0px_#000] space-y-4">
            <p className="text-xs font-black text-[#ff7a1b] uppercase tracking-wider">Profile</p>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-400 uppercase">Email Address</label>
                <input
                  type="email"
                  value={availEmail}
                  onChange={(e) => setAvailEmail(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="you@gobitsnbytes.org"
                />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-400 uppercase">Timezone</label>
                <select
                  value={availTimezone}
                  onChange={(e) => setAvailTimezone(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-400 uppercase">Display Title</label>
                <input
                  type="text"
                  value={availTitle}
                  onChange={(e) => setAvailTitle(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="e.g. Fork Organizer"
                />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-400 uppercase">Booking Handle</label>
                <div className="flex items-center border-2 border-black rounded-base overflow-hidden bg-[#222]">
                  <span className="text-gray-600 text-xs font-bold px-2 border-r border-neutral-700 bg-[#1a1a1a] py-2.5 shrink-0">cal.gobitsnbytes.org/</span>
                  <input
                    type="text"
                    value={availBookingLink}
                    onChange={(e) => setAvailBookingLink(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                    className="flex-1 bg-transparent p-2 text-white text-sm focus:outline-none"
                    placeholder="your-handle"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-bold text-gray-400 uppercase">Short Bio / Booking Description</label>
              <textarea
                value={availDescription}
                onChange={(e) => setAvailDescription(e.target.value)}
                rows={2}
                className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b] resize-none"
                placeholder="Short description shown on your booking card"
              />
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-bold text-gray-400 uppercase">Cal.com Event Type ID (optional)</label>
              <input
                type="text"
                value={availCalcomId}
                onChange={(e) => setAvailCalcomId(e.target.value)}
                className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                placeholder="e.g. 12345"
              />
            </div>
          </div>

          {/* Weekly availability grid */}
          <div className="border-2 border-black bg-[#161412] rounded-base p-4 shadow-[2px_2px_0px_0px_#000] space-y-3">
            <div>
              <p className="text-xs font-black text-[#ff7a1b] uppercase tracking-wider">Weekly Availability Hours</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Set which hours guests can book. Uses your timezone above.
              </p>
            </div>
            <AvailabilityGrid
              value={availWeeklyHours}
              onChange={setAvailWeeklyHours}
            />
          </div>

          {/* Push notification note */}
          <div className="flex items-start gap-3 p-3 border-2 border-neutral-800 rounded-base bg-[#111] text-xs text-gray-500">
            <Bell className="size-4 shrink-0 text-gray-600 mt-0.5" />
            <span>
              To enable Web Push notifications for booking alerts,{" "}
              <a
                href="https://cal.gobitsnbytes.org/dashboard"
                target="_blank"
                rel="noreferrer"
                className="text-[#ff7a1b] hover:underline"
              >
                open your chrono dashboard →
              </a>
            </span>
          </div>

          <button
            type="submit"
            disabled={availLoading}
            className="flex items-center justify-center gap-2 w-full p-3 font-bold border-2 border-black bg-green-400 text-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000] transition-all rounded-base disabled:opacity-50"
          >
            <Save className="size-4 shrink-0" />
            {availLoading ? "Saving…" : "Save Availability"}
          </button>
        </form>
      )}

      {/* ── Tab: Notifications ───────────────────────────────────────────── */}
      {activeTab === "notifications" && (
        <form onSubmit={handleSavePreferences} className="space-y-5 max-w-lg">
          <div>
            <h2 className="text-2xl font-heading font-black text-white">NOTIFICATIONS</h2>
            <p className="text-xs text-gray-400 mt-1">Configure how you get notified about meetings.</p>
          </div>

          {prefSuccess && (
            <div className="bg-green-950 text-green-200 border-2 border-green-800 p-3 rounded-base font-bold text-sm flex items-center gap-2">
              <CheckCircle className="size-4 shrink-0" />
              Preferences saved!
            </div>
          )}

          <div className="border-2 border-black bg-[#161412] rounded-base p-4 shadow-[2px_2px_0px_0px_#000] space-y-4">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-gray-400 uppercase">Notification Email</label>
              <input
                type="email"
                value={prefEmail}
                onChange={(e) => setPrefEmail(e.target.value)}
                required
                className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                placeholder="you@example.com"
              />
            </div>
            <div className="space-y-3 pt-1">
              <label className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={prefNotifyInvite}
                  onChange={(e) => setPrefNotifyInvite(e.target.checked)}
                  className="size-5 rounded border-2 border-black bg-[#222] text-[#ff7a1b] focus:ring-0"
                />
                <span className="text-sm text-gray-200 font-bold">Email me when invited to a new meeting</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={prefNotifyReminder}
                  onChange={(e) => setPrefNotifyReminder(e.target.checked)}
                  className="size-5 rounded border-2 border-black bg-[#222] text-[#ff7a1b] focus:ring-0"
                />
                <span className="text-sm text-gray-200 font-bold">Reminder 30 mins before call starts</span>
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={prefLoading}
            className="flex items-center justify-center gap-2 w-full p-3 font-bold border-2 border-black bg-green-400 text-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000] transition-all rounded-base disabled:opacity-50"
          >
            <Save className="size-4 shrink-0" />
            {prefLoading ? "Saving…" : "Save Preferences"}
          </button>
        </form>
      )}

      {/* ── Schedule Modal ───────────────────────────────────────────────── */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="border-4 border-black bg-[#12100e] max-w-xl w-full max-h-[90vh] overflow-y-auto p-6 rounded-base shadow-[8px_8px_0px_0px_#000]">
            <div className="flex justify-between items-center border-b-2 border-neutral-800 pb-3 mb-4">
              <h2 className="text-xl font-heading font-black text-white uppercase">Schedule Internal Call</h2>
              <button onClick={() => setShowScheduleModal(false)} className="text-gray-400 hover:text-white">
                <X className="size-5" />
              </button>
            </div>
            <form onSubmit={handleScheduleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Meeting Title</label>
                <input type="text" required value={scheduleTitle} onChange={(e) => setScheduleTitle(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="e.g. Tech Fork Sync" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Agenda</label>
                <textarea value={scheduleDesc} onChange={(e) => setScheduleDesc(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b] h-16 resize-none"
                  placeholder="Brief description or agenda notes" />
              </div>
              <div className="grid gap-3 grid-cols-3">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Date</label>
                  <input type="date" required value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]" />
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Time</label>
                  <input type="time" required value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]" />
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Duration</label>
                  <select value={scheduleDuration} onChange={(e) => setScheduleDuration(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]">
                    <option value="15">15 min</option>
                    <option value="30">30 min</option>
                    <option value="45">45 min</option>
                    <option value="60">60 min</option>
                    <option value="90">90 min</option>
                  </select>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Location</label>
                  <select value={scheduleLocationType} onChange={(e) => setScheduleLocationType(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]">
                    <option value="discord_vc">Discord Voice Channel</option>
                    <option value="external">External URL</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Location Details</label>
                  <input type="text" value={scheduleLocationDetails} onChange={(e) => setScheduleLocationDetails(e.target.value)}
                    disabled={scheduleLocationType === "discord_vc"}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b] disabled:opacity-40"
                    placeholder="External link or VC name" />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Join Scope</label>
                  <select value={scheduleScope} onChange={(e) => setScheduleScope(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]">
                    <option value="invite">Invite Only</option>
                    <option value="open">Open (All contributors)</option>
                    <option value="hq">HQ Only</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Invitees (Discord ID CSV)</label>
                  <input type="text" value={scheduleInvitees} onChange={(e) => setScheduleInvitees(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                    placeholder="snowflake_1, snowflake_2" />
                </div>
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">External Guest Emails</label>
                <input type="text" value={scheduleEmails} onChange={(e) => setScheduleEmails(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="guest@example.com, another@example.com" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Private Notes</label>
                <input type="text" value={scheduleNotes} onChange={(e) => setScheduleNotes(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="Included in email invites and ICS calendars" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowScheduleModal(false)}
                  className="w-1/2 p-3 border-2 border-black bg-neutral-800 text-white hover:bg-neutral-700 font-bold rounded-base text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={scheduleLoading}
                  className="w-1/2 p-3 border-2 border-black bg-main text-main-foreground shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none font-bold rounded-base text-sm disabled:opacity-50">
                  {scheduleLoading ? "Scheduling…" : "Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Reschedule Modal ─────────────────────────────────────────────── */}
      {showRescheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="border-4 border-black bg-[#12100e] max-w-sm w-full p-6 rounded-base shadow-[8px_8px_0px_0px_#000]">
            <div className="flex justify-between items-center border-b-2 border-neutral-800 pb-3 mb-4">
              <h2 className="text-lg font-heading font-black text-white uppercase">Reschedule</h2>
              <button onClick={() => setShowRescheduleModal(null)} className="text-gray-400 hover:text-white">
                <X className="size-5" />
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-4 font-bold">{showRescheduleModal.title}</p>
            <form onSubmit={handleReschedule} className="space-y-3">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">New Date</label>
                <input type="date" required value={reschedDate} onChange={(e) => setReschedDate(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">New Time</label>
                <input type="time" required value={reschedTime} onChange={(e) => setReschedTime(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b]" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Reason</label>
                <textarea value={reschedReason} onChange={(e) => setReschedReason(e.target.value)} rows={2}
                  className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white text-sm focus:outline-none focus:border-[#ff7a1b] resize-none"
                  placeholder="Brief reason for rescheduling (sent to attendees)" />
              </div>
              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setShowRescheduleModal(null)}
                  className="w-1/2 p-2.5 border-2 border-black bg-neutral-800 text-white font-bold rounded-base text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={reschedLoading}
                  className="w-1/2 p-2.5 border-2 border-black bg-[#ff7a1b] text-black font-bold rounded-base shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none text-sm disabled:opacity-50">
                  {reschedLoading ? "Rescheduling…" : "Confirm"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Meeting Detail Modal ─────────────────────────────────────────── */}
      {selectedMeeting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="border-4 border-black bg-[#12100e] max-w-4xl w-full max-h-[92vh] overflow-y-auto p-6 rounded-base shadow-[8px_8px_0px_0px_#000]">
            {/* Header */}
            <div className="flex justify-between items-start border-b-2 border-neutral-800 pb-3 mb-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-heading font-black text-white uppercase truncate">
                    {selectedMeeting.title}
                  </h2>
                  <span className={`text-xs font-black uppercase px-2 py-0.5 border border-black rounded-full shrink-0 ${getStatusColor(selectedMeeting.status)}`}>
                    {selectedMeeting.status}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400 mt-1">
                  <span>📅 {formatTime(selectedMeeting.scheduled_time)}</span>
                  <span>📍 {selectedMeeting.location_details ?? selectedMeeting.location_type}</span>
                  {selectedMeeting.meet_code && (
                    <span className="text-[#ff7a1b] font-mono">🔗 {selectedMeeting.meet_code}</span>
                  )}
                </div>
              </div>
              <button onClick={() => setSelectedMeeting(null)} className="text-gray-400 hover:text-white ml-4 shrink-0">
                <X className="size-5" />
              </button>
            </div>

            {/* Action bar */}
            <div className="flex flex-wrap gap-2 mb-4">
              {selectedMeeting.status === "active" && selectedMeeting.temp_channel_id && (
                <a
                  href={`discord://discordapp.com/channels/${selectedMeeting.temp_channel_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-black bg-green-400 text-black rounded shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                >
                  Join VC
                </a>
              )}
              {selectedMeeting.meet_code && (
                <a
                  href={`https://cal.gobitsnbytes.org/m/${selectedMeeting.meet_code}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-black bg-[#222] text-white rounded hover:bg-[#333] transition-colors"
                >
                  <ExternalLink className="size-3.5" />
                  Open Meeting Page
                </a>
              )}
              {selectedMeeting.status === "scheduled" && (
                <>
                  <button
                    onClick={() => { setShowRescheduleModal(selectedMeeting); setSelectedMeeting(null); }}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-black bg-[#222] text-white rounded hover:bg-[#333] transition-colors"
                  >
                    <RefreshCw className="size-3.5" />
                    Reschedule
                  </button>
                  <button
                    onClick={() => handleCancelMeeting(selectedMeeting.id)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-black bg-red-500 text-black rounded shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                  >
                    Cancel Meeting
                  </button>
                </>
              )}
            </div>

            {/* Description */}
            <div className="bg-neutral-900 border-2 border-black p-3.5 rounded-base text-sm text-gray-300 mb-5">
              <span className="block text-xs font-bold text-[#ff7a1b] uppercase mb-1">Agenda</span>
              {selectedMeeting.description ?? "No agenda description provided."}
            </div>

            {/* Transcript */}
            {selectedMeeting.status === "completed" && selectedMeeting.transcript ? (
              <div className="space-y-5">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="md:col-span-2 border-2 border-black bg-neutral-900/50 p-4 rounded-base">
                    <span className="flex items-center gap-1.5 text-xs font-black text-[#ff7a1b] uppercase mb-2">
                      <FileText className="size-4 shrink-0" />AI Meeting Summary
                    </span>
                    <p className="text-xs text-gray-300 leading-relaxed">
                      {selectedMeeting.transcript.summary ?? "No summary available."}
                    </p>
                  </div>
                  <div className="border-2 border-black bg-neutral-900/50 p-4 rounded-base">
                    <span className="flex items-center gap-1.5 text-xs font-black text-[#ff7a1b] uppercase mb-2">
                      <CheckCircle className="size-4 shrink-0" />Key Decisions
                    </span>
                    <ul className="list-disc pl-4 text-xs text-gray-300 space-y-1.5">
                      {parseStringArray(selectedMeeting.transcript.key_decisions).length === 0 ? (
                        <li className="text-gray-500 italic">No explicit decisions recorded.</li>
                      ) : (
                        parseStringArray(selectedMeeting.transcript.key_decisions).map((dec, i) => (
                          <li key={i}>{dec}</li>
                        ))
                      )}
                    </ul>
                  </div>
                </div>

                {/* Action items */}
                <div className="border-2 border-black bg-neutral-900/50 p-4 rounded-base">
                  <span className="flex items-center gap-1.5 text-xs font-black text-[#ff7a1b] uppercase mb-3">
                    <Clock className="size-4 shrink-0" />Action Items
                  </span>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead>
                        <tr className="border-b-2 border-black text-gray-400 font-bold">
                          <th className="pb-2">Assignee</th>
                          <th className="pb-2">Task</th>
                          <th className="pb-2">Deadline</th>
                          <th className="pb-2">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {parseActionItems(selectedMeeting.transcript.action_items).length === 0 ? (
                          <tr><td colSpan={4} className="py-2 text-gray-500 italic text-center">No action items recorded.</td></tr>
                        ) : (
                          parseActionItems(selectedMeeting.transcript.action_items).map((item, i) => (
                            <tr key={i} className="border-b border-neutral-800 last:border-b-0">
                              <td className="py-2.5 font-bold text-white">{item.assignee}</td>
                              <td className="py-2.5 text-gray-300">{item.task}</td>
                              <td className="py-2.5 text-gray-400">{item.deadline || "—"}</td>
                              <td className="py-2.5">
                                <span className="px-2 py-0.5 bg-yellow-950 text-yellow-300 border border-yellow-800 rounded font-bold uppercase text-[10px]">
                                  Pending
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Searchable transcript */}
                <div className="border-2 border-black bg-neutral-900/50 p-4 rounded-base space-y-3">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-neutral-800 pb-2">
                    <span className="text-xs font-black text-[#ff7a1b] uppercase">Dialogue Transcript</span>
                    <div className="relative w-full sm:w-64">
                      <Search className="absolute left-2.5 top-2.5 size-4 text-gray-500" />
                      <input
                        type="text"
                        placeholder="Search speakers / text…"
                        value={transcriptSearch}
                        onChange={(e) => setTranscriptSearch(e.target.value)}
                        className="w-full bg-[#111] border border-black pl-9 pr-2.5 py-1.5 rounded text-xs text-white focus:outline-none focus:border-[#ff7a1b]"
                      />
                    </div>
                  </div>
                  <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
                    {!selectedMeeting.transcript.timestamped_transcript ? (
                      <p className="text-xs text-gray-500 italic">No dialogue transcript available.</p>
                    ) : (
                      selectedMeeting.transcript.timestamped_transcript
                        .split("\n")
                        .filter((line) => !transcriptSearch || line.toLowerCase().includes(transcriptSearch.toLowerCase()))
                        .map((line, idx) => {
                          const match = line.match(/^\[(\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$/);
                          if (match) {
                            const [, time, speaker, speech] = match;
                            return (
                              <div key={idx} className="text-xs flex gap-2">
                                <span className="text-[#ff7a1b] font-bold select-none shrink-0">[{time}]</span>
                                <span className="text-white font-bold shrink-0">{speaker}:</span>
                                <span className="text-gray-300">{speech}</span>
                              </div>
                            );
                          }
                          return <div key={idx} className="text-xs text-gray-400 italic">{line}</div>;
                        })
                    )}
                  </div>
                </div>
              </div>
            ) : selectedMeeting.status === "completed" ? (
              <div className="border-2 border-black bg-neutral-900/50 p-6 text-center text-gray-400 font-bold rounded-base">
                Transcript post-processing in progress…
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
