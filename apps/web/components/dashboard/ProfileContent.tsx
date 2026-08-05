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
      <div className="rounded-xl border-2 border-border bg-[#111] p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-5">
          <div className="relative size-16 shrink-0 rounded-full border-2 border-amber-400 overflow-hidden bg-main/20 flex items-center justify-center">
            {session?.user?.image ? (
              <img src={session.user.image} alt={form.display_name} className="size-full object-cover" />
            ) : (
              <User className="size-8 text-amber-400" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-heading font-bold text-foreground">{form.display_name || "Team Member"}</h2>
              <Badge variant="success" className="flex items-center gap-1 text-[10px]">
                <ShieldCheck className="size-3" /> Chrono v2 Verified
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">{form.title}</p>
            <p className="text-xs text-white/60 mt-1 max-w-lg">{form.bio}</p>
          </div>
        </div>

        <div className="flex flex-col gap-2 text-right text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5 justify-end">
            <MapPin className="size-3.5 text-amber-400" />
            <span>{form.timezone}</span>
          </div>
          <div className="flex items-center gap-1.5 justify-end">
            <Clock className="size-3.5 text-emerald-400" />
            <span>Chrono v2: {form.chrono_work_start} - {form.chrono_work_end}</span>
          </div>
        </div>
      </div>

      {successMsg && (
        <div className="rounded-xl border-2 border-emerald-500/50 bg-emerald-500/10 p-4 text-xs font-bold text-emerald-400 flex items-center gap-2">
          <CheckCircle2 className="size-4" />
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="rounded-xl border-2 border-destructive/50 bg-destructive/10 p-4 text-xs font-bold text-destructive">
          {errorMsg}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSave} className="grid gap-6 md:grid-cols-2">
        {/* Basic Profile */}
        <Card className="rounded-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <User className="size-4 text-amber-400" /> Basic Team Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="display_name">Display Name *</Label>
              <Input
                id="display_name"
                value={form.display_name}
                onChange={(e) => setForm((prev) => ({ ...prev, display_name: e.target.value }))}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="title">Role / Operational Title</Label>
              <Input
                id="title"
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="e.g. Lead Engineer, Operations Manager, Founder"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="bio">Bio / Strategic Focus</Label>
              <Input
                id="bio"
                value={form.bio}
                onChange={(e) => setForm((prev) => ({ ...prev, bio: e.target.value }))}
                placeholder="What are you building or driving at bits&bytes?"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="timezone">Timezone & Location</Label>
              <Input
                id="timezone"
                value={form.timezone}
                onChange={(e) => setForm((prev) => ({ ...prev, timezone: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="skillsStr">Skills & Stack (comma-separated)</Label>
              <Input
                id="skillsStr"
                value={form.skillsStr}
                onChange={(e) => setForm((prev) => ({ ...prev, skillsStr: e.target.value }))}
                placeholder="Next.js, Python, FastAPI, Docker, Design"
              />
            </div>
          </CardContent>
        </Card>

        {/* Chrono v2 System Preferences */}
        <Card className="rounded-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4 text-purple-400" /> Chrono v2 System Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Configure your single-source availability schedule. Chrono v2 uses these preferences for meeting matching and Discord role sync.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="work_start">Work Start (Local)</Label>
                <Input
                  id="work_start"
                  type="time"
                  value={form.chrono_work_start}
                  onChange={(e) => setForm((prev) => ({ ...prev, chrono_work_start: e.target.value }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="work_end">Work End (Local)</Label>
                <Input
                  id="work_end"
                  type="time"
                  value={form.chrono_work_end}
                  onChange={(e) => setForm((prev) => ({ ...prev, chrono_work_end: e.target.value }))}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="call_pref">Preferred Communication Channel</Label>
              <Input
                id="call_pref"
                value={form.chrono_call_preference}
                onChange={(e) => setForm((prev) => ({ ...prev, chrono_call_preference: e.target.value }))}
                placeholder="Discord Voice, Cal.com, Google Meet"
              />
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="auto_sync"
                checked={form.chrono_auto_sync}
                onChange={(e) => setForm((prev) => ({ ...prev, chrono_auto_sync: e.target.checked }))}
                className="size-4 rounded border-border"
              />
              <Label htmlFor="auto_sync" className="text-xs cursor-pointer">
                Enable auto-sync with Discord Roles & Notion Members Table
              </Label>
            </div>

            <Button type="submit" disabled={saving} className="w-full mt-4">
              {saving ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" /> Saving Profile...
                </>
              ) : (
                <>
                  <Save className="mr-2 size-4" /> Save Team Profile (Apply Everywhere)
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
