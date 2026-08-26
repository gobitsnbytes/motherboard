"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { User, CheckCircle2, Clock, Sparkles, MapPin, Globe, Loader2, Save, ShieldCheck } from "lucide-react";
import { Badge, Button, Input, Card, CardContent, CardHeader, CardTitle, Label } from "@bnb/ui";
import { ProfileSkeleton } from "./Skeletons";

export function ProfileContent() {
  const { data: session, update: updateSession } = useSession();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [form, setForm] = useState({
    display_name: "",
    email: "",
    title: "",
    bio: "",
    timezone: "Asia/Kolkata (IST +5:30)",
    skillsStr: "Next.js, Python, FastAPI, TypeScript",
    chrono_work_start: "10:00",
    chrono_work_end: "19:00",
    chrono_call_preference: "discord",
    chrono_auto_sync: true,
  });

  const fetchProfile = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/users/me");
      if (res.ok) {
        const data = await res.json();
        setForm({
          display_name: data.display_name || session?.user?.name || "",
          email: data.email || session?.user?.email || "",
          title: data.title || "Core Team Contributor",
          bio: data.bio || "Building the alternative for ambitious teenagers to ship tech.",
          timezone: data.timezone || "Asia/Kolkata (IST +5:30)",
          skillsStr: data.skills ? data.skills.join(", ") : "Next.js, Python, FastAPI, TypeScript",
          chrono_work_start: data.chrono_v2_data?.work_start || "10:00",
          chrono_work_end: data.chrono_v2_data?.work_end || "19:00",
          chrono_call_preference: data.chrono_v2_data?.call_preference || "discord",
          chrono_auto_sync: data.chrono_v2_data?.auto_sync ?? true,
        });
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Failed to load profile data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    const skills = form.skillsStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      display_name: form.display_name,
      title: form.title,
      bio: form.bio,
      timezone: form.timezone,
      skills,
      chrono_v2_data: {
        work_start: form.chrono_work_start,
        work_end: form.chrono_work_end,
        call_preference: form.chrono_call_preference,
        auto_sync: form.chrono_auto_sync,
        updated_at: new Date().toISOString(),
      },
      profile_completed: true,
    };

    try {
      const res = await fetch("/api/users/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSuccessMsg("Team profile & Chrono v2 preferences updated successfully!");
        if (updateSession) updateSession();
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || "Failed to update profile.");
      }
    } catch (e) {
      console.error(e);
      setErrorMsg("An unexpected error occurred while saving profile.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <ProfileSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="rounded-base border-2 border-border bg-[#141418] p-6 flex flex-col md:flex-row items-center justify-between gap-6 shadow-dark">
        <div className="flex items-center gap-5">
          <div className="relative size-16 shrink-0 rounded-base border-2 border-orange overflow-hidden bg-black flex items-center justify-center shadow-light">
            {session?.user?.image ? (
              <img src={session.user.image} alt={form.display_name} className="size-full object-cover" />
            ) : (
              <User className="size-8 text-orange" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-heading font-black text-white uppercase tracking-tight">{form.display_name || "Team Member"}</h2>
              <span className="flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-base border border-emerald-800 bg-emerald-950 text-emerald-400">
                <ShieldCheck className="size-3" /> Chrono v2 Verified
              </span>
            </div>
            <p className="text-xs font-mono text-orange mt-0.5">{form.title}</p>
            <p className="text-xs text-zinc-300 mt-1 max-w-lg font-base">{form.bio}</p>
          </div>
        </div>

        <div className="flex flex-col gap-2 text-right text-xs font-mono text-zinc-400">
          <div className="flex items-center gap-1.5 justify-end">
            <MapPin className="size-3.5 text-orange" />
            <span>{form.timezone}</span>
          </div>
          <div className="flex items-center gap-1.5 justify-end">
            <Clock className="size-3.5 text-emerald-400" />
            <span className="text-zinc-300">Chrono: {form.chrono_work_start} - {form.chrono_work_end}</span>
          </div>
        </div>
      </div>

      {successMsg && (
        <div className="rounded-base border-2 border-emerald-600 bg-emerald-950/80 p-4 text-xs font-mono font-bold text-emerald-300 flex items-center gap-2 shadow-light">
          <CheckCircle2 className="size-4" />
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="rounded-base border-2 border-red-500 bg-red-950/80 p-4 text-xs font-mono font-bold text-red-200 shadow-light">
          {errorMsg}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSave} className="grid gap-6 md:grid-cols-2">
        {/* Basic Profile */}
        <Card className="rounded-base border-2 border-border bg-[#141418] shadow-dark">
          <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
            <CardTitle className="flex items-center gap-2 font-heading font-black text-sm uppercase tracking-wider text-white">
              <User className="size-4 text-orange" /> Basic Team Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <div className="space-y-1.5">
              <Label htmlFor="display_name" className="text-xs font-mono font-bold uppercase text-zinc-300">Display Name *</Label>
              <Input
                id="display_name"
                value={form.display_name}
                onChange={(e) => setForm((prev) => ({ ...prev, display_name: e.target.value }))}
                required
                className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="title" className="text-xs font-mono font-bold uppercase text-zinc-300">Role / Operational Title</Label>
              <Input
                id="title"
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="e.g. Lead Engineer, Operations Manager, Founder"
                className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="bio" className="text-xs font-mono font-bold uppercase text-zinc-300">Bio / Strategic Focus</Label>
              <Input
                id="bio"
                value={form.bio}
                onChange={(e) => setForm((prev) => ({ ...prev, bio: e.target.value }))}
                placeholder="What are you building or driving at bits&bytes?"
                className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="timezone" className="text-xs font-mono font-bold uppercase text-zinc-300">Timezone & Location</Label>
              <Input
                id="timezone"
                value={form.timezone}
                onChange={(e) => setForm((prev) => ({ ...prev, timezone: e.target.value }))}
                className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="skillsStr" className="text-xs font-mono font-bold uppercase text-zinc-300">Skills & Stack (comma-separated)</Label>
              <Input
                id="skillsStr"
                value={form.skillsStr}
                onChange={(e) => setForm((prev) => ({ ...prev, skillsStr: e.target.value }))}
                placeholder="Next.js, Python, FastAPI, Docker, Design"
                className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
              />
            </div>
          </CardContent>
        </Card>

        {/* Chrono v2 System Preferences */}
        <Card className="rounded-base border-2 border-border bg-[#141418] shadow-dark">
          <CardHeader className="border-b-2 border-border bg-[#121216] py-3.5">
            <CardTitle className="flex items-center gap-2 font-heading font-black text-sm uppercase tracking-wider text-white">
              <Sparkles className="size-4 text-orange" /> Chrono v2 System Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <p className="text-xs text-zinc-300 font-mono">
              Configure your single-source availability schedule. Chrono v2 uses these preferences for meeting matching and Discord role sync.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="work_start" className="text-xs font-mono font-bold uppercase text-zinc-300">Work Start (Local)</Label>
                <Input
                  id="work_start"
                  type="time"
                  value={form.chrono_work_start}
                  onChange={(e) => setForm((prev) => ({ ...prev, chrono_work_start: e.target.value }))}
                  className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="work_end" className="text-xs font-mono font-bold uppercase text-zinc-300">Work End (Local)</Label>
                <Input
                  id="work_end"
                  type="time"
                  value={form.chrono_work_end}
                  onChange={(e) => setForm((prev) => ({ ...prev, chrono_work_end: e.target.value }))}
                  className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="call_pref" className="text-xs font-mono font-bold uppercase text-zinc-300">Preferred Communication Channel</Label>
              <Input
                id="call_pref"
                value={form.chrono_call_preference}
                onChange={(e) => setForm((prev) => ({ ...prev, chrono_call_preference: e.target.value }))}
                placeholder="Discord Voice, Cal.com, Google Meet"
                className="bg-black border-2 border-border text-white text-xs font-mono shadow-light"
              />
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="auto_sync"
                checked={form.chrono_auto_sync}
                onChange={(e) => setForm((prev) => ({ ...prev, chrono_auto_sync: e.target.checked }))}
                className="size-4 rounded-base border-2 border-border bg-black accent-orange cursor-pointer"
              />
              <Label htmlFor="auto_sync" className="text-xs font-mono text-zinc-300 cursor-pointer">
                Enable auto-sync with Discord Roles & Notion Members Table
              </Label>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full mt-4 flex items-center justify-center gap-2 px-5 py-2.5 font-heading font-black text-xs uppercase tracking-wider bg-orange text-black border-2 border-black rounded-base shadow-light hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" /> Saving Profile...
                </>
              ) : (
                <>
                  <Save className="mr-2 size-4" /> Save Team Profile (Apply Everywhere)
                </>
              )}
            </button>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
