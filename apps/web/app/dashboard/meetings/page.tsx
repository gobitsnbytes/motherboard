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
  FileSpreadsheet,
  Braces,
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
  Globe,
  Link2,
} from "lucide-react";
import AvailabilityGrid from "../../../components/dashboard/AvailabilityGrid";
import ChronoHostGrid from "../../../components/dashboard/ChronoHostGrid";
import ChronoBookingPanel from "../../../components/dashboard/ChronoBookingPanel";
import MeetingsAgendaCalendar from "../../../components/dashboard/MeetingsAgendaCalendar";

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
  recording_url?: string | null;
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

type ActiveTab = "meetings" | "book" | "availability" | "notifications" | "calendar";

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
    case "active": return "bg-green-200 text-green-900 border-green-800 animate-pulse motion-reduce:animate-none";
    case "completed": return "bg-gray-200 text-gray-900 border-gray-800";
    case "cancelled": return "bg-red-200 text-red-900 border-red-800";
    default: return "bg-white text-black border-border";
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

function downloadFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportActionItemsCSV(meeting: Meeting) {
  const items = parseActionItems(meeting.transcript?.action_items ?? null);
  const rows = [
    ["Meeting Title", "Assignee", "Task Deliverable", "Deadline", "Status"],
    ...items.map(it => [
      meeting.title,
      it.assignee || "Unassigned",
      it.task || "",
      it.deadline || "None",
      "Pending"
    ])
  ];
  const csvContent = rows.map(r => r.map(cell => `"${(cell || "").replace(/"/g, '""')}"`).join(",")).join("\n");
  downloadFile(`action_items_${meeting.id}.csv`, csvContent, "text/csv;charset=utf-8;");
}

function exportActionItemsJSON(meeting: Meeting) {
  const items = parseActionItems(meeting.transcript?.action_items ?? null);
  const data = {
    meeting_id: meeting.id,
    meeting_title: meeting.title,
    scheduled_time: meeting.scheduled_time,
    action_items: items.map(it => ({
      assignee: it.assignee || "Unassigned",
      task: it.task || "",
      deadline: it.deadline || null,
      status: "pending"
    }))
  };
  downloadFile(`action_items_${meeting.id}.json`, JSON.stringify(data, null, 2), "application/json");
}

function exportActionItemsMarkdown(meeting: Meeting) {
  const items = parseActionItems(meeting.transcript?.action_items ?? null);
  let md = `# Action Item Deliverables: ${meeting.title}\n\n`;
  md += `- **Date**: ${formatTime(meeting.scheduled_time)}\n`;
  md += `- **Total Deliverables**: ${items.length}\n\n`;
  md += `| Assignee | Task Deliverable | Deadline | Status |\n`;
  md += `| --- | --- | --- | --- |\n`;
  for (const it of items) {
    md += `| ${it.assignee || "Unassigned"} | ${it.task || ""} | ${it.deadline || "None"} | Pending |\n`;
  }
  downloadFile(`action_items_${meeting.id}.md`, md, "text/markdown;charset=utf-8;");
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 font-heading font-bold border-2 border-border rounded-t-base transition-all text-sm whitespace-nowrap ${
        active
          ? "bg-orange text-black shadow-shadow translate-y-[-2px]"
          : "bg-neutral-800 text-white hover:bg-neutral-700"
      }`}
    >
      {label}
    </button>
  );
}

const RECORDING_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  transcribed: "Transcribed",
};

function RecordingChip({ meeting }: { meeting: Meeting }) {
  const status = (meeting.recording_status ?? "").toLowerCase();
  const label = RECORDING_LABELS[status];
  if (!label) return null;
  const url = meeting.recording_url ?? null;
  return (
    <div className="flex items-center gap-2 text-gray-300 min-w-0">
      <span
        className={`size-2 rounded-full shrink-0 ${status === "transcribed" ? "bg-green-400" : "bg-orange"}`}
        aria-hidden="true"
      />
      <span className="truncate">Recording: {label}</span>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="shrink-0 text-xs font-bold underline underline-offset-2 hover:text-orange transition-colors"
          aria-label={`Open recording for ${meeting.title}`}
        >
          Listen
        </a>
      )}
    </div>
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

  // Status filter state for meetings tab
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [meetingSearch, setMeetingSearch] = useState<string>("");

  const filteredMeetings = meetings.filter((m) => {
    const matchesStatus = statusFilter === "all" || m.status === statusFilter;
    const matchesSearch =
      !meetingSearch ||
      m.title.toLowerCase().includes(meetingSearch.toLowerCase()) ||
      (m.description && m.description.toLowerCase().includes(meetingSearch.toLowerCase())) ||
      (m.meet_code && m.meet_code.toLowerCase().includes(meetingSearch.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  const activeCount = meetings.filter((m) => m.status === "active").length;
  const scheduledCount = meetings.filter((m) => m.status === "scheduled").length;

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4 sm:p-6 lg:p-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-dark border-4 border-border p-5 rounded-base shadow-shadow">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-heading font-black tracking-tight text-white flex items-center gap-3">
              MEETINGS & SCHEDULING
            </h1>
            <span className="text-xs font-black bg-orange text-black border-2 border-border px-2.5 py-0.5 rounded shadow-shadow">
              chrono v2
            </span>
            {activeCount > 0 && (
              <span className="text-xs font-black bg-green-400 text-black border-2 border-border px-2.5 py-0.5 rounded animate-pulse motion-reduce:animate-none">
                ● {activeCount} LIVE NOW
              </span>
            )}
          </div>
          <p className="text-xs sm:text-sm text-gray-400 mt-1">
            Manage availability, schedule calls, book syncs, and access AI-generated transcripts.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowScheduleModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 font-heading font-bold border-2 border-border bg-orange text-black shadow-shadow hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all rounded-base text-sm"
          >
            <Plus className="size-4 shrink-0" />
            Schedule Internal Call
          </button>
        </div>
      </div>

      {/* ⚡ Instant Meet Banner */}
      <div className="border-4 border-border bg-orange/10 rounded-base p-4 shadow-shadow">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="size-4 text-orange shrink-0" />
          <span className="text-sm font-black text-white uppercase tracking-wider">Instant Voice Channel</span>
          <span className="text-xs text-gray-400">— spin up a live temporary Discord VC with AI recording right now</span>
        </div>
        {instantResult ? (
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 p-3 bg-green-950 border-2 border-green-800 rounded-base">
            <CheckCircle className="size-5 text-green-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-green-200">Meeting Room Live!</p>
              <p className="text-xs text-green-400 font-mono mt-0.5">
                cal.gobitsnbytes.org/m/{instantResult.meet_code}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(`https://cal.gobitsnbytes.org/m/${instantResult.meet_code}`)}
                className="text-xs font-bold px-3 py-1.5 border-2 border-green-700 bg-green-900 text-green-200 rounded hover:bg-green-800 transition-colors"
              >
                Copy Room Link
              </button>
              <button
                type="button"
                onClick={() => setInstantResult(null)}
                className="text-xs font-bold px-3 py-1.5 border-2 border-border bg-neutral-800 text-white rounded hover:bg-neutral-700 transition-colors"
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
              placeholder="Meeting topic (e.g. Fork Onboarding, Architecture Review…)"
              className="flex-1 bg-neutral-800 border-2 border-border p-2.5 rounded-base text-sm text-white focus:outline-none focus:border-orange"
            />
            <select
              value={instantScope}
              onChange={(e) => setInstantScope(e.target.value)}
              className="bg-neutral-800 border-2 border-border p-2.5 rounded-base text-sm text-white focus:outline-none focus:border-orange w-full sm:w-48 shrink-0"
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
              className="flex items-center justify-center gap-2 px-5 py-2.5 font-heading font-bold border-2 border-border bg-orange text-black shadow-shadow hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all rounded-base text-sm shrink-0 disabled:opacity-50"
            >
              <Zap className="size-4 shrink-0" />
              {instantLoading ? "Launching…" : "Start Now"}
            </button>
          </form>
        )}
      </div>

      {/* Booking success banner */}
      {bookingSuccess && (
        <div className="flex items-center gap-3 p-4 bg-green-950 border-4 border-border text-green-200 text-sm font-bold rounded-base shadow-shadow">
          <CheckCircle className="size-5 shrink-0 text-green-400" />
          Booking confirmed! Calendar invite dispatched and notification sent to all participants.
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex gap-2 border-b-4 border-border pb-2 overflow-x-auto">
        <TabButton label={`My Meetings (${meetings.length})`} active={activeTab === "meetings"} onClick={() => setActiveTab("meetings")} />
        <TabButton label="Book a Sync" active={activeTab === "book"} onClick={() => setActiveTab("book")} />
        <TabButton label="My Availability" active={activeTab === "availability"} onClick={() => setActiveTab("availability")} />
        <TabButton label="Notification Preferences" active={activeTab === "notifications"} onClick={() => setActiveTab("notifications")} />
        <TabButton label="Calendar" active={activeTab === "calendar"} onClick={() => setActiveTab("calendar")} />
      </div>

      {/* ── Tab 5: Calendar ────────────────────────────────────────────────── */}
      {activeTab === "calendar" && (
        <MeetingsAgendaCalendar
          meetings={meetings}
          loading={loading}
          onSelectMeeting={(m) => setSelectedMeeting(meetings.find((x) => x.id === m.id) ?? null)}
        />
      )}

      {/* ── Tab 1: My Meetings ─────────────────────────────────────────────── */}
      {activeTab === "meetings" && (
        <div className="space-y-4">
          {/* Controls: Search and Status Filters */}
          <div className="flex flex-col sm:flex-row justify-between gap-3 bg-dark border-2 border-border p-3 rounded-base shadow-shadow">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 size-4 text-gray-500" />
              <input
                type="text"
                placeholder="Search meetings by title, agenda, or meet code…"
                value={meetingSearch}
                onChange={(e) => setMeetingSearch(e.target.value)}
                className="w-full bg-neutral-800 border-2 border-border pl-9 pr-3 py-1.5 rounded-base text-xs sm:text-sm text-white focus:outline-none focus:border-orange"
              />
            </div>
            <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
              {["all", "scheduled", "active", "completed", "cancelled"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1.5 text-xs font-bold uppercase rounded-base border-2 border-border transition-colors ${
                    statusFilter === st
                      ? "bg-orange text-black"
                      : "bg-neutral-800 text-gray-400 hover:text-white"
                  }`}
                >
                  {st} {st === "scheduled" && scheduledCount > 0 ? `(${scheduledCount})` : st === "active" && activeCount > 0 ? `(${activeCount})` : ""}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="border-4 border-border bg-neutral-900 p-12 text-center text-white font-bold rounded-base shadow-shadow">
              <RefreshCw className="size-8 animate-spin motion-reduce:animate-none mx-auto mb-2 text-orange" />
              Loading your meetings schedule…
            </div>
          ) : error ? (
            <div className="border-4 border-border bg-red-950 text-red-200 p-4 font-bold rounded-base flex items-center gap-3 shadow-shadow">
              <AlertTriangle className="size-6 shrink-0 text-red-400" />
              <span className="flex-1">{error}</span>
              <button onClick={fetchMeetings} className="px-3 py-1 bg-red-900 border border-border rounded text-xs font-bold">Retry</button>
            </div>
          ) : filteredMeetings.length === 0 ? (
            <div className="border-4 border-border bg-neutral-900 p-12 text-center rounded-base shadow-shadow">
              <CalendarClock className="size-12 mx-auto mb-3 text-gray-600" />
              <p className="text-white font-black text-lg">No meetings found</p>
              <p className="text-xs text-gray-400 mt-1">
                {statusFilter !== "all" || meetingSearch ? "Try adjusting your search query or status filter." : "Use Instant Voice Channel, Schedule, or Book a Sync to get started."}
              </p>
            </div>
          ) : (
            <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
              {filteredMeetings.map((meeting) => (
                <div
                  key={meeting.id}
                  onClick={() => setSelectedMeeting(meeting)}
                  className="border-4 border-border bg-dark p-5 rounded-base shadow-shadow cursor-pointer transition-all hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_var(--border)] flex flex-col justify-between"
                >
                  <div>
                    <div className="flex justify-between items-start gap-2 mb-2">
                      <h2 className="text-base font-heading font-black text-white line-clamp-1">{meeting.title}</h2>
                      <span className={`text-[10px] font-black uppercase px-2 py-0.5 border-2 border-border rounded-full shrink-0 ${getStatusColor(meeting.status)}`}>
                        {meeting.status}
                      </span>
                    </div>
                    {meeting.description && (
                      <p className="text-xs text-gray-400 line-clamp-2 mb-3">{meeting.description}</p>
                    )}
                    <div className="space-y-1.5 bg-black/40 p-3 border-2 border-border rounded-base text-xs">
                      <div className="flex items-center gap-2 text-gray-300">
                        <Clock className="size-3.5 text-orange shrink-0" />
                        <span>{formatTime(meeting.scheduled_time)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-300">
                        <MapPin className="size-3.5 text-orange shrink-0" />
                        <span className="truncate">{meeting.location_type === "discord_vc" ? "Discord Voice Channel" : meeting.location_details || "External Call"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-300">
                        <Users className="size-3.5 text-orange shrink-0" />
                        <span>{meeting.attendees?.length || 1} participant(s)</span>
                      </div>
                      <RecordingChip meeting={meeting} />
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t-2 border-neutral-800 flex justify-between items-center gap-2">
                    <span className="text-[11px] text-gray-500 font-mono truncate">
                      {meeting.meet_code ? `code: ${meeting.meet_code}` : "no code"}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                      {meeting.status === "active" && meeting.temp_channel_id && (
                        <a
                          href={`discord://discordapp.com/channels/${meeting.temp_channel_id}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs font-black px-2.5 py-1 bg-green-400 text-black border-2 border-border rounded hover:bg-green-300 transition-colors"
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
                          className="text-gray-400 hover:text-orange transition-colors p-1"
                          title="Open meeting portal page"
                          aria-label="Open meeting portal page"
                        >
                          <ExternalLink className="size-4" />
                        </a>
                      )}
                      {meeting.status === "completed" && (
                        <span className="flex items-center gap-1 text-xs font-bold text-green-400 bg-green-950 px-2 py-0.5 border border-green-800 rounded">
                          <FileText className="size-3 shrink-0" />
                          Brief
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

      {/* ── Tab 2: Book a Sync ─────────────────────────────────────────────── */}
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
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-heading font-black text-white">BOOK A SYNC</h2>
                  <p className="text-xs text-gray-400">Select a team member to view their availability and schedule a call.</p>
                </div>
                <a
                  href="https://cal.gobitsnbytes.org"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-xs font-bold text-orange border-2 border-border bg-neutral-800 px-3 py-1.5 rounded-base hover:bg-neutral-700 transition-colors shadow-shadow"
                >
                  <ExternalLink className="size-3.5" />
                  Public Portal
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

      {/* ── Tab 3: My Availability (Full-Width Responsive 2-Column Layout) ─── */}
      {activeTab === "availability" && (
        <form onSubmit={handleSaveAvailability} className="space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b-2 border-neutral-800 pb-3">
            <div>
              <h2 className="text-2xl font-heading font-black text-white">MY AVAILABILITY & BOOKING PROFILE</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Configure your public booking handle, bio, and weekly availability hours for guest scheduling.
              </p>
            </div>
            {availBookingLink && (
              <a
                href={`https://cal.gobitsnbytes.org/${availBookingLink}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 text-xs font-bold text-orange border-2 border-border bg-orange/10 px-3 py-1.5 rounded-base hover:bg-orange/20 transition-colors shrink-0"
              >
                <ExternalLink className="size-3.5" />
                cal.gobitsnbytes.org/{availBookingLink}
              </a>
            )}
          </div>

          {availSuccess && (
            <div className="bg-green-950 text-green-200 border-4 border-border p-4 rounded-base font-bold text-sm flex items-center gap-3 shadow-shadow">
              <CheckCircle className="size-5 shrink-0 text-green-400" />
              <span>Availability settings saved! Your public booking page is now active and updated.</span>
            </div>
          )}

          {/* 2-Column Responsive Dashboard Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Profile Settings & Live Card Preview */}
            <div className="lg:col-span-5 space-y-5">
              <div className="border-4 border-border bg-dark rounded-base p-5 shadow-shadow space-y-4">
                <p className="text-xs font-black text-orange uppercase tracking-wider border-b-2 border-neutral-800 pb-2">
                  1. Profile Details
                </p>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-gray-300 uppercase">Email Address</label>
                  <input
                    type="email"
                    value={availEmail}
                    onChange={(e) => setAvailEmail(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                    placeholder="you@gobitsnbytes.org"
                  />
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-gray-300 uppercase">Timezone</label>
                  <select
                    value={availTimezone}
                    onChange={(e) => setAvailTimezone(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-gray-300 uppercase">Display Title / Role</label>
                  <input
                    type="text"
                    value={availTitle}
                    onChange={(e) => setAvailTitle(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                    placeholder="e.g. CTO, Fork Lead, Dev Lead"
                  />
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-gray-300 uppercase">Custom Booking Handle</label>
                  <div className="flex items-center border-2 border-border rounded-base overflow-hidden bg-neutral-800">
                    <span className="text-gray-500 text-xs font-mono font-bold px-2.5 py-2.5 border-r border-neutral-800 bg-neutral-800 shrink-0 select-none">
                      cal.gobitsnbytes.org/
                    </span>
                    <input
                      type="text"
                      value={availBookingLink}
                      onChange={(e) => setAvailBookingLink(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                      className="flex-1 bg-transparent p-2.5 text-white text-sm focus:outline-none font-mono"
                      placeholder="your-handle"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-gray-300 uppercase">Short Bio / Booking Description</label>
                  <textarea
                    value={availDescription}
                    onChange={(e) => setAvailDescription(e.target.value)}
                    rows={3}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange resize-none"
                    placeholder="Brief intro shown to guests when booking a sync with you"
                  />
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-gray-400 uppercase">Cal.com Event Type ID (Optional)</label>
                  <input
                    type="text"
                    value={availCalcomId}
                    onChange={(e) => setAvailCalcomId(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                    placeholder="e.g. 12345"
                  />
                </div>
              </div>

              {/* Live Preview Card */}
              <div className="border-4 border-border bg-black/40 rounded-base p-5 shadow-shadow space-y-3">
                <div className="flex justify-between items-center border-b border-neutral-800 pb-2">
                  <span className="text-xs font-black text-orange uppercase tracking-wider flex items-center gap-1.5">
                    <Zap className="size-3.5" /> Guest Preview
                  </span>
                  <span className="text-[10px] text-gray-500 font-mono">Public Card</span>
                </div>
                <div className="border-2 border-border bg-dark p-4 rounded-base space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-full border-2 border-border bg-orange text-black font-black flex items-center justify-center text-base">
                      {username.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <h4 className="text-sm font-black text-white">{username}</h4>
                      <p className="text-xs text-orange font-bold">{availTitle || "Team Member"}</p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 line-clamp-2">
                    {availDescription || "Available for 1-on-1 syncs, fork discussions, and technical reviews."}
                  </p>
                  <div className="flex justify-between items-center pt-2 border-t border-neutral-800 text-[11px] text-gray-500">
                    <span className="inline-flex items-center gap-1"><Globe className="size-3 shrink-0" /> {availTimezone}</span>
                    <span className="font-mono text-orange">cal.gobitsnbytes.org/{availBookingLink || "..."}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Weekly Availability Hours Editor */}
            <div className="lg:col-span-7 space-y-5">
              <div className="border-4 border-border bg-dark rounded-base p-5 shadow-shadow space-y-4">
                <div className="flex justify-between items-start border-b-2 border-neutral-800 pb-3">
                  <div>
                    <p className="text-xs font-black text-orange uppercase tracking-wider">
                      2. Weekly Availability Schedule
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Toggle days and set specific hours when guests can book calls with you. (Times match your timezone).
                    </p>
                  </div>
                </div>

                <AvailabilityGrid
                  value={availWeeklyHours}
                  onChange={setAvailWeeklyHours}
                />
              </div>

              {/* Web push notification note */}
              <div className="flex items-start gap-3 p-4 border-2 border-border rounded-base bg-neutral-800/60 text-xs text-gray-400 shadow-shadow">
                <Bell className="size-4 shrink-0 text-orange mt-0.5" />
                <span>
                  <strong>Web Push & Discord Alerts:</strong> Bookings created through your link will trigger immediate Discord DMs and browser push notifications.
                </span>
              </div>

              {/* Save Button */}
              <button
                type="submit"
                disabled={availLoading}
                className="flex items-center justify-center gap-2 w-full p-4 font-heading font-black text-base border-4 border-border bg-green-400 text-black shadow-shadow hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all rounded-base disabled:opacity-50"
              >
                <Save className="size-5 shrink-0" />
                {availLoading ? "Saving Availability Settings…" : "Save Availability Settings"}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* ── Tab 4: Notifications (Balanced 2-Column Layout) ────────────────── */}
      {activeTab === "notifications" && (
        <form onSubmit={handleSavePreferences} className="space-y-6">
          <div className="border-b-2 border-neutral-800 pb-3">
            <h2 className="text-2xl font-heading font-black text-white">NOTIFICATION PREFERENCES</h2>
            <p className="text-xs text-gray-400 mt-0.5">Manage how and when you receive meeting invites and reminder alerts.</p>
          </div>

          {prefSuccess && (
            <div className="bg-green-950 text-green-200 border-4 border-border p-4 rounded-base font-bold text-sm flex items-center gap-3 shadow-shadow">
              <CheckCircle className="size-5 shrink-0 text-green-400" />
              <span>Notification preferences updated successfully!</span>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 border-4 border-border bg-dark rounded-base p-5 shadow-shadow space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-300 uppercase">Notification Email Address</label>
                <input
                  type="email"
                  value={prefEmail}
                  onChange={(e) => setPrefEmail(e.target.value)}
                  required
                  className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                  placeholder="you@example.com"
                />
              </div>

              <div className="space-y-3 pt-2 border-t border-neutral-800">
                <label className="flex items-start gap-3 cursor-pointer select-none p-2 rounded hover:bg-neutral-800 transition-colors">
                  <input
                    type="checkbox"
                    checked={prefNotifyInvite}
                    onChange={(e) => setPrefNotifyInvite(e.target.checked)}
                    className="mt-0.5 size-5 rounded border-2 border-border bg-neutral-800 text-orange focus:ring-0"
                  />
                  <div>
                    <span className="text-sm text-gray-200 font-bold block">Email on New Invitations</span>
                    <span className="text-xs text-gray-500">Send an instant email notification whenever you are invited to a call.</span>
                  </div>
                </label>

                <label className="flex items-start gap-3 cursor-pointer select-none p-2 rounded hover:bg-neutral-800 transition-colors">
                  <input
                    type="checkbox"
                    checked={prefNotifyReminder}
                    onChange={(e) => setPrefNotifyReminder(e.target.checked)}
                    className="mt-0.5 size-5 rounded border-2 border-border bg-neutral-800 text-orange focus:ring-0"
                  />
                  <div>
                    <span className="text-sm text-gray-200 font-bold block">30-Minute Call Reminder</span>
                    <span className="text-xs text-gray-500">Send a reminder alert 30 minutes before any scheduled meeting starts.</span>
                  </div>
                </label>
              </div>

              <button
                type="submit"
                disabled={prefLoading}
                className="flex items-center justify-center gap-2 w-full p-3 font-heading font-bold border-2 border-border bg-green-400 text-black shadow-shadow hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all rounded-base disabled:opacity-50 mt-4"
              >
                <Save className="size-4 shrink-0" />
                {prefLoading ? "Saving Preferences…" : "Save Notification Preferences"}
              </button>
            </div>

            <div className="lg:col-span-5 border-4 border-border bg-black/40 rounded-base p-5 shadow-shadow space-y-4">
              <span className="text-xs font-black text-orange uppercase tracking-wider block border-b border-neutral-800 pb-2">
                Automated Integrations
              </span>
              <div className="space-y-3 text-xs text-gray-400">
                <div className="p-3 bg-neutral-800/60 border-2 border-border rounded-base space-y-1">
                  <p className="font-bold text-white flex items-center gap-2">
                    <Bell className="size-3.5 text-orange" /> Discord DM Dispatch
                  </p>
                  <p>Bot automatically pings your Discord account when a room opens or recording is finalized.</p>
                </div>
                <div className="p-3 bg-neutral-800/60 border-2 border-border rounded-base space-y-1">
                  <p className="font-bold text-white flex items-center gap-2">
                    <CalendarIcon className="size-3.5 text-orange" /> Calendar ICS Sync
                  </p>
                  <p>All scheduled meetings attach standard .ics calendar files compatible with Google Calendar, Apple Calendar, and Outlook.</p>
                </div>
              </div>
            </div>
          </div>
        </form>
      )}

      {/* ── Schedule Modal ───────────────────────────────────────────────── */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="border-4 border-border bg-dark max-w-xl w-full max-h-[90vh] overflow-y-auto p-6 rounded-base shadow-shadow">
            <div className="flex justify-between items-center border-b-2 border-neutral-800 pb-3 mb-4">
              <h2 className="text-xl font-heading font-black text-white uppercase">Schedule Internal Call</h2>
              <button onClick={() => setShowScheduleModal(false)} aria-label="Close schedule dialog" className="text-gray-400 hover:text-white">
                <X className="size-5" />
              </button>
            </div>
            <form onSubmit={handleScheduleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Meeting Title</label>
                <input type="text" required value={scheduleTitle} onChange={(e) => setScheduleTitle(e.target.value)}
                  className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                  placeholder="e.g. Tech Fork Sync" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Agenda</label>
                <textarea value={scheduleDesc} onChange={(e) => setScheduleDesc(e.target.value)}
                  className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange h-16 resize-none"
                  placeholder="Brief description or agenda notes" />
              </div>
              <div className="grid gap-3 grid-cols-3">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-orange uppercase">Date</label>
                  <input type="date" required value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2 rounded-base text-white text-sm focus:outline-none focus:border-orange" />
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-orange uppercase">Time</label>
                  <input type="time" required value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2 rounded-base text-white text-sm focus:outline-none focus:border-orange" />
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-orange uppercase">Duration</label>
                  <select value={scheduleDuration} onChange={(e) => setScheduleDuration(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange">
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
                  <label className="block text-xs font-bold text-orange uppercase">Location</label>
                  <select value={scheduleLocationType} onChange={(e) => setScheduleLocationType(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange">
                    <option value="discord_vc">Discord Voice Channel</option>
                    <option value="external">External URL</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-orange uppercase">Location Details</label>
                  <input type="text" value={scheduleLocationDetails} onChange={(e) => setScheduleLocationDetails(e.target.value)}
                    disabled={scheduleLocationType === "discord_vc"}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange disabled:opacity-40"
                    placeholder="External link or VC name" />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-orange uppercase">Join Scope</label>
                  <select value={scheduleScope} onChange={(e) => setScheduleScope(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange">
                    <option value="invite">Invite Only</option>
                    <option value="open">Open (All contributors)</option>
                    <option value="hq">HQ Only</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-orange uppercase">Invitees (Discord ID CSV)</label>
                  <input type="text" value={scheduleInvitees} onChange={(e) => setScheduleInvitees(e.target.value)}
                    className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                    placeholder="snowflake_1, snowflake_2" />
                </div>
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">External Guest Emails</label>
                <input type="text" value={scheduleEmails} onChange={(e) => setScheduleEmails(e.target.value)}
                  className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                  placeholder="guest@example.com, another@example.com" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Private Notes</label>
                <input type="text" value={scheduleNotes} onChange={(e) => setScheduleNotes(e.target.value)}
                  className="w-full bg-neutral-800 border-2 border-border p-2.5 rounded-base text-white text-sm focus:outline-none focus:border-orange"
                  placeholder="Included in email invites and ICS calendars" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowScheduleModal(false)}
                  className="w-1/2 p-3 border-2 border-border bg-neutral-800 text-white hover:bg-neutral-700 font-bold rounded-base text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={scheduleLoading}
                  className="w-1/2 p-3 border-2 border-border bg-orange text-black shadow-shadow hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none font-heading font-bold rounded-base text-sm disabled:opacity-50">
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
          <div className="border-4 border-border bg-dark max-w-sm w-full p-6 rounded-base shadow-shadow">
            <div className="flex justify-between items-center border-b-2 border-neutral-800 pb-3 mb-4">
              <h2 className="text-lg font-heading font-black text-white uppercase">Reschedule Call</h2>
              <button onClick={() => setShowRescheduleModal(null)} aria-label="Close reschedule dialog" className="text-gray-400 hover:text-white">
                <X className="size-5" />
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-4 font-bold">{showRescheduleModal.title}</p>
            <form onSubmit={handleReschedule} className="space-y-3">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">New Date</label>
                <input type="date" required value={reschedDate} onChange={(e) => setReschedDate(e.target.value)}
                  className="w-full bg-neutral-800 border-2 border-border p-2 rounded-base text-white text-sm focus:outline-none focus:border-orange" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">New Time</label>
                <input type="time" required value={reschedTime} onChange={(e) => setReschedTime(e.target.value)}
                  className="w-full bg-neutral-800 border-2 border-border p-2 rounded-base text-white text-sm focus:outline-none focus:border-orange" />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-bold text-orange uppercase">Reason</label>
                <textarea value={reschedReason} onChange={(e) => setReschedReason(e.target.value)} rows={2}
                  className="w-full bg-neutral-800 border-2 border-border p-2 rounded-base text-white text-sm focus:outline-none focus:border-orange resize-none"
                  placeholder="Brief reason for rescheduling (sent to attendees)" />
              </div>
              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setShowRescheduleModal(null)}
                  className="w-1/2 p-2.5 border-2 border-border bg-neutral-800 text-white font-bold rounded-base text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={reschedLoading}
                  className="w-1/2 p-2.5 border-2 border-border bg-orange text-black font-heading font-bold rounded-base shadow-shadow hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none text-sm disabled:opacity-50">
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
          <div className="border-4 border-border bg-dark max-w-4xl w-full max-h-[92vh] overflow-y-auto p-6 rounded-base shadow-shadow">
            {/* Header */}
            <div className="flex justify-between items-start border-b-2 border-neutral-800 pb-3 mb-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-heading font-black text-white uppercase truncate">
                    {selectedMeeting.title}
                  </h2>
                  <span className={`text-xs font-black uppercase px-2 py-0.5 border border-border rounded-full shrink-0 ${getStatusColor(selectedMeeting.status)}`}>
                    {selectedMeeting.status}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400 mt-1">
                  <span className="inline-flex items-center gap-1"><CalendarIcon className="size-3.5 shrink-0" /> {formatTime(selectedMeeting.scheduled_time)}</span>
                  <span className="inline-flex items-center gap-1"><MapPin className="size-3.5 shrink-0" /> {selectedMeeting.location_details ?? selectedMeeting.location_type}</span>
                  {selectedMeeting.meet_code && (
                    <span className="text-orange font-mono inline-flex items-center gap-1"><Link2 className="size-3.5 shrink-0" /> {selectedMeeting.meet_code}</span>
                  )}
                  <RecordingChip meeting={selectedMeeting} />
                </div>
              </div>
              <button onClick={() => setSelectedMeeting(null)} aria-label="Close meeting details" className="text-gray-400 hover:text-white ml-4 shrink-0">
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
                  className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-border bg-green-400 text-black rounded shadow-shadow hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                >
                  Join VC
                </a>
              )}
              {selectedMeeting.meet_code && (
                <a
                  href={`https://cal.gobitsnbytes.org/m/${selectedMeeting.meet_code}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-border bg-neutral-800 text-white rounded hover:bg-neutral-700 transition-colors"
                >
                  <ExternalLink className="size-3.5" />
                  Open Meeting Page
                </a>
              )}
              {selectedMeeting.status === "scheduled" && (
                <>
                  <button
                    onClick={() => { setShowRescheduleModal(selectedMeeting); setSelectedMeeting(null); }}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-border bg-neutral-800 text-white rounded hover:bg-neutral-700 transition-colors"
                  >
                    <RefreshCw className="size-3.5" />
                    Reschedule
                  </button>
                  <button
                    onClick={() => handleCancelMeeting(selectedMeeting.id)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-black border-2 border-border bg-red-500 text-black rounded shadow-shadow hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                  >
                    Cancel Meeting
                  </button>
                </>
              )}
            </div>

            {/* Description */}
            <div className="bg-neutral-900 border-2 border-border p-3.5 rounded-base text-sm text-gray-300 mb-5">
              <span className="block text-xs font-bold text-orange uppercase mb-1">Agenda</span>
              {selectedMeeting.description ?? "No agenda description provided."}
            </div>

            {/* Transcript */}
            {selectedMeeting.status === "completed" && selectedMeeting.transcript ? (
              <div className="space-y-5">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="md:col-span-2 border-2 border-border bg-neutral-900/50 p-4 rounded-base">
                    <span className="flex items-center gap-1.5 text-xs font-black text-orange uppercase mb-2">
                      <FileText className="size-4 shrink-0" />AI Meeting Summary
                    </span>
                    <p className="text-xs text-gray-300 leading-relaxed">
                      {selectedMeeting.transcript.summary ?? "No summary available."}
                    </p>
                  </div>
                  <div className="border-2 border-border bg-neutral-900/50 p-4 rounded-base">
                    <span className="flex items-center gap-1.5 text-xs font-black text-orange uppercase mb-2">
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
                <div className="border-2 border-border bg-neutral-900/50 p-4 rounded-base">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                    <span className="flex items-center gap-1.5 text-xs font-black text-orange uppercase">
                      <Clock className="size-4 shrink-0" />Action Items Deliverables
                    </span>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] text-gray-400 font-bold uppercase mr-1">Export:</span>
                      <button
                        onClick={() => exportActionItemsCSV(selectedMeeting)}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-bold border-2 border-border bg-neutral-800 text-white rounded hover:bg-orange hover:text-black transition-colors"
                        title="Download CSV report"
                      >
                        <FileSpreadsheet className="size-3 shrink-0" />
                        CSV
                      </button>
                      <button
                        onClick={() => exportActionItemsJSON(selectedMeeting)}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-bold border-2 border-border bg-neutral-800 text-white rounded hover:bg-orange hover:text-black transition-colors"
                        title="Download JSON format"
                      >
                        <Braces className="size-3 shrink-0" />
                        JSON
                      </button>
                      <button
                        onClick={() => exportActionItemsMarkdown(selectedMeeting)}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-bold border-2 border-border bg-neutral-800 text-white rounded hover:bg-orange hover:text-black transition-colors"
                        title="Download Markdown summary"
                      >
                        <FileText className="size-3 shrink-0" />
                        Markdown
                      </button>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead>
                        <tr className="border-b-2 border-border text-gray-400 font-bold">
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
                <div className="border-2 border-border bg-neutral-900/50 p-4 rounded-base space-y-3">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-neutral-800 pb-2">
                    <span className="text-xs font-black text-orange uppercase">Dialogue Transcript</span>
                    <div className="relative w-full sm:w-64">
                      <Search className="absolute left-2.5 top-2.5 size-4 text-gray-500" />
                      <input
                        type="text"
                        placeholder="Search speakers / text…"
                        value={transcriptSearch}
                        onChange={(e) => setTranscriptSearch(e.target.value)}
                        className="w-full bg-black/40 border border-border pl-9 pr-2.5 py-1.5 rounded text-xs text-white focus:outline-none focus:border-orange"
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
                                <span className="text-orange font-bold select-none shrink-0">[{time}]</span>
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
              <div className="border-2 border-border bg-neutral-900/50 p-6 text-center text-gray-400 font-bold rounded-base">
                Transcript post-processing in progress…
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
