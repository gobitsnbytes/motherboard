"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Users, Clock, Globe, ExternalLink, Zap } from "lucide-react";

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

interface ChronoHostGridProps {
  onSelectHost: (host: HostProfile) => void;
  selectedHostLink?: string | null;
  apiBase: string; // The FastAPI base URL, e.g. process.env.NEXT_PUBLIC_API_URL or window origin
}

function HostCard({
  host,
  selected,
  onClick,
}: {
  host: HostProfile;
  selected: boolean;
  onClick: () => void;
}) {
  const avatarUrl = host.avatar
    ? `https://cdn.discordapp.com/avatars/${host.discord_id}/${host.avatar}.webp?size=128`
    : null;

  const initials = (host.username || "?")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left p-4 border-2 rounded-base transition-all ${
        selected
          ? "border-[#ff7a1b] bg-[#1f1810] shadow-[4px_4px_0px_0px_#ff7a1b]"
          : "border-black bg-[#161412] hover:bg-[#1a1816] shadow-[2px_2px_0px_0px_#000] hover:shadow-[4px_4px_0px_0px_#000] hover:translate-x-[-1px] hover:translate-y-[-1px]"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="shrink-0">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt={host.username}
              className="w-12 h-12 rounded-full border-2 border-black object-cover"
            />
          ) : (
            <div className="w-12 h-12 rounded-full border-2 border-black bg-[#97192c] flex items-center justify-center font-black text-white text-sm">
              {initials}
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 justify-between">
            <span className="font-black text-white text-sm truncate">{host.username}</span>
            {selected && (
              <span className="text-[10px] font-black bg-[#ff7a1b] text-black px-2 py-0.5 rounded-full border border-black shrink-0">
                Selected
              </span>
            )}
          </div>
          {host.title && (
            <p className="text-xs text-[#ff7a1b] font-bold mt-0.5 truncate">{host.title}</p>
          )}
          {host.description && (
            <p className="text-xs text-gray-400 mt-1 line-clamp-2">{host.description}</p>
          )}
          <div className="flex items-center gap-1.5 mt-2 text-[10px] text-gray-500">
            <Globe className="size-3 shrink-0" />
            <span className="truncate">{host.timezone || "Asia/Kolkata"}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

export default function ChronoHostGrid({ onSelectHost, selectedHostLink, apiBase }: ChronoHostGridProps) {
  const [hosts, setHosts] = useState<HostProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${apiBase}/api/meetings/public/hosts`);
        if (!res.ok) throw new Error("Failed to load team members");
        const data: HostProfile[] = await res.json();
        setHosts(data.filter((h) => h.booking_link));
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load team members");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [apiBase]);

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="p-4 border-2 border-black bg-[#161412] rounded-base shadow-[2px_2px_0px_0px_#000] animate-pulse"
          >
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-full bg-neutral-800 shrink-0" />
              <div className="flex-1 space-y-2 pt-1">
                <div className="h-3 bg-neutral-800 rounded w-3/4" />
                <div className="h-2 bg-neutral-800 rounded w-1/2" />
                <div className="h-2 bg-neutral-800 rounded w-full" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-2 border-black bg-red-950 text-red-200 p-4 rounded-base font-bold text-sm">
        {error}
      </div>
    );
  }

  if (hosts.length === 0) {
    return (
      <div className="border-2 border-black bg-[#161412] p-8 rounded-base text-center text-gray-500">
        <Users className="size-8 mx-auto mb-2 opacity-30" />
        <p className="font-bold">No team members have set up their booking profiles yet.</p>
        <p className="text-xs mt-1">Set up your availability in the "My Availability" tab to appear here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Select a team member to see their available slots and book a sync.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {hosts.map((host) => (
          <HostCard
            key={host.discord_id}
            host={host}
            selected={selectedHostLink === host.booking_link}
            onClick={() => onSelectHost(host)}
          />
        ))}
      </div>
    </div>
  );
}
