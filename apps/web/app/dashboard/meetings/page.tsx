"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Users,
  Video,
  FileText,
  AlertTriangle,
  Plus,
  Save,
  CheckCircle,
  XCircle,
  HelpCircle,
  Search,
} from "lucide-react";

interface MeetingAttendee {
  meeting_id: string;
  attendee_type: string;
  discord_id: string;
}

interface MeetingTranscript {
  meeting_id: string;
  summary: string | null;
  key_decisions: string | null; // JSON string
  action_items: string | null;  // JSON string
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
  status: string; // 'scheduled', 'active', 'completed', 'cancelled'
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

interface MeetingEmailPreference {
  discord_id: string;
  email: string;
  notify_on_invite: number;
  notify_on_reminder: number;
}

export default function MeetingsPage() {
  const { data: session } = useSession();
  const discordId = session?.user?.discordId;
  const username = session?.user?.name || "User";
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<"meetings" | "availability" | "preferences">("meetings");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);

  // Form states - Schedule
  const [scheduleTitle, setScheduleTitle] = useState("");
  const [scheduleDesc, setScheduleDesc] = useState("");
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [scheduleDuration, setScheduleDuration] = useState("30");
  const [scheduleLocationType, setScheduleLocationType] = useState("discord_vc");
  const [scheduleLocationDetails, setScheduleLocationDetails] = useState("");
  const [scheduleScope, setScheduleScope] = useState("invite");
  const [scheduleInvitees, setScheduleInvitees] = useState(""); // Comma separated Discord IDs/Role IDs
  const [scheduleEmails, setScheduleEmails] = useState(""); // Comma separated guest emails
  const [scheduleNotes, setScheduleNotes] = useState("");
  const [scheduleLoading, setScheduleLoading] = useState(false);

  // Form states - Availability
  const [availEmail, setAvailEmail] = useState("");
  const [availTimezone, setAvailTimezone] = useState("Asia/Kolkata");
  const [availWeeklyHours, setAvailWeeklyHours] = useState("");
  const [availBookingLink, setAvailBookingLink] = useState("");
  const [availTitle, setAvailTitle] = useState("");
  const [availDescription, setAvailDescription] = useState("");
  const [availLoading, setAvailLoading] = useState(false);
  const [availSuccess, setAvailSuccess] = useState(false);

  // Form states - Preferences
  const [prefEmail, setPrefEmail] = useState("");
  const [prefNotifyInvite, setPrefNotifyInvite] = useState(true);
  const [prefNotifyReminder, setPrefNotifyReminder] = useState(true);
  const [prefLoading, setPrefLoading] = useState(false);
  const [prefSuccess, setPrefSuccess] = useState(false);

  // Transcript Search filter
  const [transcriptSearch, setTranscriptSearch] = useState("");

  const fetchMeetings = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/meetings");
      if (!res.ok) throw new Error("Failed to load meetings");
      const data = await res.json();
      setMeetings(data);
    } catch (err: unknown) {
      if (err instanceof Response && err.status === 401) {
        router.push("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load meetings");
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailability = async () => {
    if (!discordId) return;
    try {
      const res = await fetch(`/api/meetings/availability/${discordId}`);
      if (res.ok) {
        const data: UserAvailability = await res.json();
        setAvailEmail(data.email || "");
        setAvailTimezone(data.timezone || "Asia/Kolkata");
        setAvailWeeklyHours(data.weekly_hours || "");
        setAvailBookingLink(data.booking_link || "");
        setAvailTitle(data.title || "");
        setAvailDescription(data.description || "");
      }
    } catch (err) {
      console.warn("Could not load availability profile:", err);
    }
  };

  const fetchPreferences = async () => {
    if (!discordId) return;
    try {
      const res = await fetch(`/api/meetings/preferences/${discordId}`);
      if (res.ok) {
        const data: MeetingEmailPreference = await res.json();
        setPrefEmail(data.email || "");
        setPrefNotifyInvite(data.notify_on_invite === 1);
        setPrefNotifyReminder(data.notify_on_reminder === 1);
      }
    } catch (err) {
      console.warn("Could not load email preferences:", err);
    }
  };

  useEffect(() => {
    fetchMeetings();
    fetchAvailability();
    fetchPreferences();
  }, [discordId]);

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!discordId) return;
    try {
      setScheduleLoading(true);
      setError(null);

      // Validate date & time
      const dateTimeStr = `${scheduleDate}T${scheduleTime}:00`;
      const scheduledTimeMs = new Date(dateTimeStr).getTime();
      if (isNaN(scheduledTimeMs)) {
        throw new Error("Invalid date or time specified");
      }

      const inviteeParts = scheduleInvitees
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const invitees = inviteeParts.map((id) => ({
        type: id.length > 15 ? "role" : "user", // Rough guess on role vs user snowflake length
        id,
      }));

      const externalEmails = scheduleEmails
        .split(",")
        .map((e) => e.trim())
        .filter((e) => e.includes("@"));

      const payload = {
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
      };

      const res = await fetch("/api/meetings/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "Failed to schedule meeting");
      }

      setShowScheduleModal(false);
      // Reset form
      setScheduleTitle("");
      setScheduleDesc("");
      setScheduleDate("");
      setScheduleTime("");
      setScheduleLocationDetails("");
      setScheduleInvitees("");
      setScheduleEmails("");
      setScheduleNotes("");
      
      // Reload meetings
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
      const payload = {
        discord_id: discordId,
        username,
        email: availEmail || null,
        timezone: availTimezone,
        weekly_hours: availWeeklyHours || null,
        booking_link: availBookingLink || null,
        title: availTitle || null,
        description: availDescription || null,
      };

      const res = await fetch("/api/meetings/availability", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
      const payload = {
        discord_id: discordId,
        email: prefEmail,
        notify_on_invite: prefNotifyInvite ? 1 : 0,
        notify_on_reminder: prefNotifyReminder ? 1 : 0,
        updated_at: Date.now()
      };

      const res = await fetch("/api/meetings/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Failed to save preferences");
      setPrefSuccess(true);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setPrefLoading(false);
    }
  };

  const cancelMeeting = async (meetingId: string) => {
    if (!confirm("Are you sure you want to cancel this meeting?")) return;
    try {
      const res = await fetch(`/api/meetings/${meetingId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to cancel meeting");
      alert("Meeting cancelled successfully");
      setSelectedMeeting(null);
      fetchMeetings();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to cancel meeting");
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case "scheduled":
        return "bg-cyan-200 text-cyan-900 border-cyan-800";
      case "active":
        return "bg-green-200 text-green-900 border-green-800 animate-pulse";
      case "completed":
        return "bg-gray-200 text-gray-900 border-gray-800";
      case "cancelled":
        return "bg-red-200 text-red-900 border-red-800";
      default:
        return "bg-white text-black border-black";
    }
  };

  const formatTime = (epoch: number) => {
    return new Date(epoch).toLocaleString("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto p-4">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-heading font-black tracking-tight text-white">
            MEETINGS & SCHEDULING
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Manage availability, schedule calls, and access AI-generated meeting transcripts.
          </p>
        </div>
        <button
          onClick={() => setShowScheduleModal(true)}
          className="flex items-center gap-2 px-5 py-3 font-bold border-2 border-black bg-main text-main-foreground shadow-[4px_4px_0px_0px_#000] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000] transition-all rounded-base"
        >
          <Plus className="size-5 shrink-0" />
          Schedule Internal Meeting
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b-4 border-black pb-2">
        <button
          onClick={() => setActiveTab("meetings")}
          className={`px-4 py-2.5 font-bold border-2 border-black rounded-t-base transition-all ${
            activeTab === "meetings"
              ? "bg-[#ff7a1b] text-black shadow-[2px_2px_0px_0px_#000] translate-y-[-2px]"
              : "bg-[#222] text-white hover:bg-[#333]"
          }`}
        >
          Meetings & Calendar
        </button>
        <button
          onClick={() => setActiveTab("availability")}
          className={`px-4 py-2.5 font-bold border-2 border-black rounded-t-base transition-all ${
            activeTab === "availability"
              ? "bg-[#ff7a1b] text-black shadow-[2px_2px_0px_0px_#000] translate-y-[-2px]"
              : "bg-[#222] text-white hover:bg-[#333]"
          }`}
        >
          My Availability
        </button>
        <button
          onClick={() => setActiveTab("preferences")}
          className={`px-4 py-2.5 font-bold border-2 border-black rounded-t-base transition-all ${
            activeTab === "preferences"
              ? "bg-[#ff7a1b] text-black shadow-[2px_2px_0px_0px_#000] translate-y-[-2px]"
              : "bg-[#222] text-white hover:bg-[#333]"
          }`}
        >
          Notification Preferences
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === "meetings" && (
        <div className="space-y-4">
          {loading ? (
            <div className="border-4 border-black bg-neutral-900 p-8 text-center text-white font-bold rounded-base shadow-[4px_4px_0px_0px_#000]">
              Loading meetings...
            </div>
          ) : error ? (
            <div className="border-4 border-black bg-red-950 text-red-200 p-4 font-bold rounded-base shadow-[4px_4px_0px_0px_#000] flex items-center gap-3">
              <AlertTriangle className="size-6 shrink-0" />
              <span>Error: {error}</span>
            </div>
          ) : meetings.length === 0 ? (
            <div className="border-4 border-black bg-neutral-900 p-8 text-center text-gray-400 font-bold rounded-base shadow-[4px_4px_0px_0px_#000]">
              No meetings scheduled. Start by scheduling one!
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
                      <h2 className="text-xl font-heading font-black text-white line-clamp-1">
                        {meeting.title}
                      </h2>
                      <span
                        className={`text-xs font-black uppercase px-2.5 py-1 border-2 border-black rounded-full ${getStatusBadgeColor(
                          meeting.status
                        )}`}
                      >
                        {meeting.status}
                      </span>
                    </div>

                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                      {meeting.description || "No agenda description."}
                    </p>

                    <div className="mt-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <Clock className="size-4 text-[#ff7a1b]" />
                        <span>{formatTime(meeting.scheduled_time)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <MapPin className="size-4 text-[#ff7a1b]" />
                        <span>
                          {meeting.location_type === "discord_vc"
                            ? "Discord Voice Channel"
                            : meeting.location_details || "External location"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <Users className="size-4 text-[#ff7a1b]" />
                        <span>{meeting.attendees?.length || 1} attendee(s)</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 pt-3 border-t-2 border-neutral-800 flex justify-between items-center text-xs">
                    <span className="text-gray-500 font-bold">Code: {meeting.meet_code || "N/A"}</span>
                    {meeting.status === "completed" && (
                      <span className="flex items-center gap-1 font-bold text-green-400">
                        <FileText className="size-4 shrink-0" />
                        AI Transcript Available
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "availability" && (
        <form
          onSubmit={handleSaveAvailability}
          className="border-4 border-black bg-[#161412] p-6 rounded-base shadow-[4px_4px_0px_0px_#000] space-y-4 max-w-2xl"
        >
          <h2 className="text-2xl font-heading font-black text-white">MY AVAILABILITY</h2>
          <p className="text-xs text-gray-400">
            Define your timezone and custom calendar booking links.
          </p>

          {availSuccess && (
            <div className="bg-green-950 text-green-200 border-2 border-green-800 p-3 rounded-base font-bold text-sm">
              ✔ Availability profile saved successfully!
            </div>
          )}

          <div className="space-y-1">
            <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Email Address</label>
            <input
              type="email"
              value={availEmail}
              onChange={(e) => setAvailEmail(e.target.value)}
              className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
              placeholder="you@gobitsnbytes.org"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Timezone</label>
            <select
              value={availTimezone}
              onChange={(e) => setAvailTimezone(e.target.value)}
              className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
            >
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">US Eastern (EST)</option>
              <option value="Europe/London">London (GMT/BST)</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Weekly Availability (JSON format or hours description)</label>
            <input
              type="text"
              value={availWeeklyHours}
              onChange={(e) => setAvailWeeklyHours(e.target.value)}
              className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
              placeholder="e.g. Mon-Fri 14:00-18:00"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Custom Booking Link (Optional)</label>
            <input
              type="url"
              value={availBookingLink}
              onChange={(e) => setAvailBookingLink(e.target.value)}
              className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
              placeholder="https://cal.gobitsnbytes.org/yourname"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Display Title</label>
              <input
                type="text"
                value={availTitle}
                onChange={(e) => setAvailTitle(e.target.value)}
                className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                placeholder="e.g. Fork Organizer"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Brief Bio/Description</label>
              <input
                type="text"
                value={availDescription}
                onChange={(e) => setAvailDescription(e.target.value)}
                className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                placeholder="Short description for bookings"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={availLoading}
            className="flex items-center justify-center gap-2 w-full mt-4 p-3 font-bold border-2 border-black bg-green-400 text-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000] transition-all rounded-base"
          >
            <Save className="size-4 shrink-0" />
            {availLoading ? "Saving..." : "Save Availability Settings"}
          </button>
        </form>
      )}

      {activeTab === "preferences" && (
        <form
          onSubmit={handleSavePreferences}
          className="border-4 border-black bg-[#161412] p-6 rounded-base shadow-[4px_4px_0px_0px_#000] space-y-4 max-w-2xl"
        >
          <h2 className="text-2xl font-heading font-black text-white">NOTIFICATION PREFERENCES</h2>
          <p className="text-xs text-gray-400">
            Configure how you want to be notified about meeting invites and reminders.
          </p>

          {prefSuccess && (
            <div className="bg-green-950 text-green-200 border-2 border-green-800 p-3 rounded-base font-bold text-sm">
              ✔ Notification preferences saved successfully!
            </div>
          )}

          <div className="space-y-1">
            <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Notification Email Address</label>
            <input
              type="email"
              value={prefEmail}
              onChange={(e) => setPrefEmail(e.target.value)}
              className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="space-y-3 pt-2">
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={prefNotifyInvite}
                onChange={(e) => setPrefNotifyInvite(e.target.checked)}
                className="size-5 rounded border-2 border-black bg-[#222] text-[#ff7a1b] focus:ring-0 cursor-pointer"
              />
              <span className="text-sm text-gray-200 font-bold">Email me when invited to a new meeting</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={prefNotifyReminder}
                onChange={(e) => setPrefNotifyReminder(e.target.checked)}
                className="size-5 rounded border-2 border-black bg-[#222] text-[#ff7a1b] focus:ring-0 cursor-pointer"
              />
              <span className="text-sm text-gray-200 font-bold">Send email reminders 30 mins before calls start</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={prefLoading}
            className="flex items-center justify-center gap-2 w-full mt-4 p-3 font-bold border-2 border-black bg-green-400 text-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000] transition-all rounded-base"
          >
            <Save className="size-4 shrink-0" />
            {prefLoading ? "Saving..." : "Save Notification Preferences"}
          </button>
        </form>
      )}

      {/* Schedule Meeting Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="border-4 border-black bg-[#12100e] max-w-xl w-full max-h-[90vh] overflow-y-auto p-6 rounded-base shadow-[8px_8px_0px_0px_#000]">
            <div className="flex justify-between items-center border-b-2 border-neutral-800 pb-3 mb-4">
              <h2 className="text-2xl font-heading font-black text-white uppercase">Schedule Call</h2>
              <button
                onClick={() => setShowScheduleModal(false)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleScheduleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Meeting Title</label>
                <input
                  type="text"
                  required
                  value={scheduleTitle}
                  onChange={(e) => setScheduleTitle(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="e.g. Tech Fork Sync"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Agenda Description</label>
                <textarea
                  value={scheduleDesc}
                  onChange={(e) => setScheduleDesc(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b] h-20"
                  placeholder="Brief description or agenda notes"
                />
              </div>

              <div className="grid gap-4 grid-cols-3">
                <div className="space-y-1 col-span-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Date</label>
                  <input
                    type="date"
                    required
                    value={scheduleDate}
                    onChange={(e) => setScheduleDate(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  />
                </div>
                <div className="space-y-1 col-span-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Time</label>
                  <input
                    type="time"
                    required
                    value={scheduleTime}
                    onChange={(e) => setScheduleTime(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  />
                </div>
                <div className="space-y-1 col-span-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Duration</label>
                  <select
                    value={scheduleDuration}
                    onChange={(e) => setScheduleDuration(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  >
                    <option value="15">15 mins</option>
                    <option value="30">30 mins</option>
                    <option value="45">45 mins</option>
                    <option value="60">60 mins</option>
                  </select>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Location Type</label>
                  <select
                    value={scheduleLocationType}
                    onChange={(e) => setScheduleLocationType(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  >
                    <option value="discord_vc">Discord Voice Channel</option>
                    <option value="external">External Meeting URL</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Location Details / URL</label>
                  <input
                    type="text"
                    value={scheduleLocationDetails}
                    onChange={(e) => setScheduleLocationDetails(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                    placeholder="External link or VC name"
                    disabled={scheduleLocationType === "discord_vc"}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Join Scope</label>
                  <select
                    value={scheduleScope}
                    onChange={(e) => setScheduleScope(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  >
                    <option value="invite">Invite Only (Explicit invitees)</option>
                    <option value="open">Open (All contributors & HQ)</option>
                    <option value="hq">HQ Only (Foundation team)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Invitees (Discord ID / Role ID CSV)</label>
                  <input
                    type="text"
                    value={scheduleInvitees}
                    onChange={(e) => setScheduleInvitees(e.target.value)}
                    className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                    placeholder="snowflake_1, snowflake_2"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">External Guest Emails (Comma separated)</label>
                <input
                  type="text"
                  value={scheduleEmails}
                  onChange={(e) => setScheduleEmails(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="guest1@example.com, guest2@example.com"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#ff7a1b] uppercase">Private Calendar Notes</label>
                <input
                  type="text"
                  value={scheduleNotes}
                  onChange={(e) => setScheduleNotes(e.target.value)}
                  className="w-full bg-[#222] border-2 border-black p-2.5 rounded-base text-white focus:outline-none focus:border-[#ff7a1b]"
                  placeholder="Visible in email invites & ICS calendars"
                />
              </div>

              <div className="flex gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowScheduleModal(false)}
                  className="w-1/2 p-3 border-2 border-black bg-neutral-800 text-white hover:bg-neutral-700 font-bold rounded-base"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={scheduleLoading}
                  className="w-1/2 p-3 border-2 border-black bg-main text-main-foreground shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] font-bold rounded-base"
                >
                  {scheduleLoading ? "Scheduling..." : "Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Meeting Detail & AI Transcript View Modal */}
      {selectedMeeting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
          <div className="border-4 border-black bg-[#12100e] max-w-4xl w-full max-h-[92vh] overflow-y-auto p-6 rounded-base shadow-[8px_8px_0px_0px_#000]">
            {/* Header */}
            <div className="flex justify-between items-start border-b-2 border-neutral-800 pb-3 mb-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-heading font-black text-white uppercase">
                    {selectedMeeting.title}
                  </h2>
                  <span
                    className={`text-xs font-black uppercase px-2 py-0.5 border border-black rounded-full ${getStatusBadgeColor(
                      selectedMeeting.status
                    )}`}
                  >
                    {selectedMeeting.status}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400 mt-1">
                  <span>📅 {formatTime(selectedMeeting.scheduled_time)}</span>
                  <span>📍 {selectedMeeting.location_details || selectedMeeting.location_type}</span>
                  {selectedMeeting.meet_code && (
                    <span className="text-[#ff7a1b]">🔗 Code: {selectedMeeting.meet_code}</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setSelectedMeeting(null)}
                className="text-gray-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            {/* Description */}
            <div className="bg-neutral-900 border-2 border-black p-3.5 rounded-base text-sm text-gray-300 mb-6">
              <span className="block text-xs font-bold text-[#ff7a1b] uppercase mb-1">AGENDA / DETAILS</span>
              {selectedMeeting.description || "No agenda description provided."}
            </div>

            {/* AI Transcripts content (if available) */}
            {selectedMeeting.status === "completed" && selectedMeeting.transcript ? (
              <div className="space-y-6">
                <div className="grid gap-4 md:grid-cols-3">
                  {/* Summary */}
                  <div className="md:col-span-2 border-2 border-black bg-neutral-900/50 p-4 rounded-base">
                    <span className="flex items-center gap-1.5 text-xs font-black text-[#ff7a1b] uppercase mb-2">
                      <FileText className="size-4 shrink-0" />
                      AI Meeting Summary
                    </span>
                    <p className="text-xs text-gray-300 leading-relaxed">
                      {selectedMeeting.transcript.summary || "No summary available."}
                    </p>
                  </div>

                  {/* Decisions */}
                  <div className="md:col-span-1 border-2 border-black bg-neutral-900/50 p-4 rounded-base">
                    <span className="flex items-center gap-1.5 text-xs font-black text-[#ff7a1b] uppercase mb-2">
                      <CheckCircle className="size-4 shrink-0" />
                      Key Decisions
                    </span>
                    <ul className="list-disc pl-4 text-xs text-gray-300 space-y-1.5">
                      {JSON.parse(selectedMeeting.transcript.key_decisions || "[]").length === 0 ? (
                        <li className="text-gray-500 italic">No explicit decisions recorded.</li>
                      ) : (
                        JSON.parse(selectedMeeting.transcript.key_decisions || "[]").map((dec: string, i: number) => (
                          <li key={i}>{dec}</li>
                        ))
                      )}
                    </ul>
                  </div>
                </div>

                {/* Action Items */}
                <div className="border-2 border-black bg-neutral-900/50 p-4 rounded-base">
                  <span className="flex items-center gap-1.5 text-xs font-black text-[#ff7a1b] uppercase mb-3">
                    <Clock className="size-4 shrink-0" />
                    Action Items & Responsibilities
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
                        {JSON.parse(selectedMeeting.transcript.action_items || "[]").length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-2 text-gray-500 italic text-center">
                              No action items recorded.
                            </td>
                          </tr>
                        ) : (
                          JSON.parse(selectedMeeting.transcript.action_items || "[]").map((item: { assignee?: string; task?: string; deadline?: string }, i: number) => (
                            <tr key={i} className="border-b border-neutral-800 last:border-b-0">
                              <td className="py-2.5 font-bold text-white">{item.assignee}</td>
                              <td className="py-2.5 text-gray-300">{item.task}</td>
                              <td className="py-2.5 text-gray-400">{item.deadline || "None"}</td>
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

                {/* Searchable Transcript */}
                <div className="border-2 border-black bg-neutral-900/50 p-4 rounded-base space-y-3">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-neutral-800 pb-2">
                    <span className="text-xs font-black text-[#ff7a1b] uppercase">
                      Dialogue Transcript
                    </span>
                    <div className="relative w-full sm:w-64">
                      <Search className="absolute left-2.5 top-2.5 size-4 text-gray-500" />
                      <input
                        type="text"
                        placeholder="Search transcript speakers/text..."
                        value={transcriptSearch}
                        onChange={(e) => setTranscriptSearch(e.target.value)}
                        className="w-full bg-[#111] border border-black pl-9 pr-2.5 py-1.5 rounded text-xs text-white focus:outline-none focus:border-[#ff7a1b]"
                      />
                    </div>
                  </div>

                  <div className="max-h-72 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-neutral-800">
                    {!selectedMeeting.transcript.timestamped_transcript ? (
                      <p className="text-xs text-gray-500 italic">No dialogue transcript available.</p>
                    ) : (
                      selectedMeeting.transcript.timestamped_transcript
                        .split("\n")
                        .filter((line) => {
                          if (!transcriptSearch) return true;
                          return line.toLowerCase().includes(transcriptSearch.toLowerCase());
                        })
                        .map((line, idx) => {
                          const match = line.match(/^\[(\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$/);
                          if (match) {
                            const [_, time, speaker, speech] = match;
                            return (
                              <div key={idx} className="text-xs flex gap-2">
                                <span className="text-[#ff7a1b] font-bold select-none">[{time}]</span>
                                <span className="text-white font-bold shrink-0">{speaker}:</span>
                                <span className="text-gray-300">{speech}</span>
                              </div>
                            );
                          }
                          return (
                            <div key={idx} className="text-xs text-gray-400 italic">
                              {line}
                            </div>
                          );
                        })
                    )}
                  </div>
                </div>
              </div>
            ) : selectedMeeting.status === "completed" ? (
              <div className="border-2 border-black bg-neutral-900/50 p-6 text-center text-gray-400 font-bold rounded-base">
                Meeting recording completed. Transcript post-processing is in progress...
              </div>
            ) : (
              <div className="border-2 border-black bg-neutral-900/50 p-6 rounded-base space-y-4">
                <div className="flex items-center gap-3 text-white font-bold text-sm">
                  <AlertTriangle className="size-5 text-yellow-500" />
                  <span>This meeting is not yet active or completed.</span>
                </div>
                <div className="flex gap-3">
                  {selectedMeeting.status === "scheduled" && (
                    <button
                      onClick={() => cancelMeeting(selectedMeeting.id)}
                      className="px-4 py-2 border-2 border-black bg-red-500 text-black font-bold text-xs shadow-[2px_2px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] rounded transition-all"
                    >
                      Cancel Meeting
                    </button>
                  )}
                  <button
                    onClick={() => setSelectedMeeting(null)}
                    className="px-4 py-2 border-2 border-black bg-neutral-800 text-white font-bold text-xs rounded"
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
