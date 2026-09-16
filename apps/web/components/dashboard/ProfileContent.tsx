"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { User, CheckCircle2, CalendarCheck2, MapPin, Loader2, Save, ShieldCheck } from "lucide-react";
import { Input, Card, CardContent, CardHeader, CardTitle, Label } from "@bnb/ui";
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
      profile_completed: true,
    };

    try {
      const res = await fetch("/api/users/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSuccessMsg("Team profile updated successfully!");
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
      <div className="rounded-base border-2 border-border bg-secondary-background p-6 flex flex-col md:flex-row items-center justify-between gap-6 shadow-dark">
        <div className="flex items-center gap-5">
          <div className="relative size-16 shrink-0 rounded-base border-2 border-orange overflow-hidden bg-muted flex items-center justify-center shadow-light">
            {session?.user?.image ? (
              <img src={session.user.image} alt={form.display_name} className="size-full object-cover" />
            ) : (
              <User className="size-8 text-orange" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-heading font-black text-foreground uppercase tracking-tight">{form.display_name || "Team Member"}</h2>
              <span className="flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-base border border-emerald-600 bg-emerald-50 text-emerald-800">
                <ShieldCheck className="size-3" /> Verified member
              </span>
            </div>
            <p className="text-xs font-mono text-orange mt-0.5">{form.title}</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-lg font-base">{form.bio}</p>
          </div>
        </div>

        <div className="flex flex-col gap-2 text-right text-xs font-mono text-muted-foreground">
          <div className="flex items-center gap-1.5 justify-end">
            <MapPin className="size-3.5 text-orange" />
            <span>{form.timezone}</span>
          </div>
        </div>
      </div>

      {successMsg && (
        <div className="rounded-base border-2 border-emerald-600 bg-emerald-50 p-4 text-xs font-mono font-bold text-emerald-800 flex items-center gap-2 shadow-light">
          <CheckCircle2 className="size-4" />
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="rounded-base border-2 border-red-500 bg-red-50 p-4 text-xs font-mono font-bold text-red-800 shadow-light">
          {errorMsg}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSave} className="grid gap-6 md:grid-cols-2">
        {/* Basic Profile */}
        <Card className="rounded-base border-2 border-border bg-secondary-background shadow-dark">
          <CardHeader className="border-b-2 border-border bg-muted py-3.5">
            <CardTitle className="flex items-center gap-2 font-heading font-black text-sm uppercase tracking-wider text-foreground">
              <User className="size-4 text-orange" /> Basic Team Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <div className="space-y-1.5">
              <Label htmlFor="display_name" className="text-xs font-mono font-bold uppercase text-muted-foreground">Display Name *</Label>
              <Input
                id="display_name"
                value={form.display_name}
                onChange={(e) => setForm((prev) => ({ ...prev, display_name: e.target.value }))}
                required
                className="bg-background border-2 border-border text-foreground text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="title" className="text-xs font-mono font-bold uppercase text-muted-foreground">Role / Operational Title</Label>
              <Input
                id="title"
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="e.g. Lead Engineer, Operations Manager, Founder"
                className="bg-background border-2 border-border text-foreground text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="bio" className="text-xs font-mono font-bold uppercase text-muted-foreground">Bio / Strategic Focus</Label>
              <Input
                id="bio"
                value={form.bio}
                onChange={(e) => setForm((prev) => ({ ...prev, bio: e.target.value }))}
                placeholder="What are you building or driving at bits&bytes?"
                className="bg-background border-2 border-border text-foreground text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="timezone" className="text-xs font-mono font-bold uppercase text-muted-foreground">Timezone & Location</Label>
              <Input
                id="timezone"
                value={form.timezone}
                onChange={(e) => setForm((prev) => ({ ...prev, timezone: e.target.value }))}
                className="bg-background border-2 border-border text-foreground text-xs font-mono shadow-light"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="skillsStr" className="text-xs font-mono font-bold uppercase text-muted-foreground">Skills & Stack (comma-separated)</Label>
              <Input
                id="skillsStr"
                value={form.skillsStr}
                onChange={(e) => setForm((prev) => ({ ...prev, skillsStr: e.target.value }))}
                placeholder="Next.js, Python, FastAPI, Docker, Design"
                className="bg-background border-2 border-border text-foreground text-xs font-mono shadow-light"
              />
            </div>
          </CardContent>
        </Card>

        {/* Scheduling ownership */}
        <Card className="rounded-base border-2 border-border bg-secondary-background shadow-dark">
          <CardHeader className="border-b-2 border-border bg-muted py-3.5">
            <CardTitle className="flex items-center gap-2 font-heading font-black text-sm uppercase tracking-wider text-foreground">
              <CalendarCheck2 className="size-4 text-orange" /> Calendar settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <p className="text-xs text-muted-foreground font-mono">
              Availability, buffers, Google Meet links, calendar writes, and booking notifications are owned by your individual Cal.com event type. Motherboard only routes bookings across verified event types.
            </p>

            <div className="rounded-base border-2 border-emerald-600 bg-emerald-50 p-4 text-xs font-mono text-emerald-900">
              No Discord voice channel, Motherboard email, or local ICS file is created for a routed booking.
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
                  <Save className="mr-2 size-4" /> Save Team Profile
                </>
              )}
            </button>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
