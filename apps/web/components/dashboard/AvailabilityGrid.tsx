"use client";

import React, { useState, useCallback, useEffect } from "react";
import { X } from "lucide-react";

// Matches the JSON format chrono's dashboard.html uses:
// { "monday": [{ "start": "09:00", "end": "17:00" }], ... }
export type DaySlot = { start: string; end: string };
export type WeeklyHoursJson = Record<string, DaySlot[]>;

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;
type Day = typeof DAYS[number];

const DAY_LABELS: Record<Day, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

const DEFAULT_START = "09:00";
const DEFAULT_END = "17:00";

interface DayRowProps {
  day: Day;
  enabled: boolean;
  slots: DaySlot[];
  onToggle: (day: Day) => void;
  onSlotChange: (day: Day, index: number, field: "start" | "end", value: string) => void;
  onAddSlot: (day: Day) => void;
  onRemoveSlot: (day: Day, index: number) => void;
  onCopyToAll: (day: Day) => void;
}

function DayRow({ day, enabled, slots, onToggle, onSlotChange, onAddSlot, onRemoveSlot, onCopyToAll }: DayRowProps) {
  return (
    <div className={`flex flex-col gap-2 p-3.5 border-2 border-border rounded-base transition-colors ${enabled ? "bg-secondary-background shadow-light" : "bg-muted"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Toggle switch */}
          <button
            type="button"
            onClick={() => onToggle(day)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-border transition-colors ${
              enabled ? "bg-orange" : "bg-muted-foreground"
            }`}
            aria-pressed={enabled}
            aria-label={`Toggle ${day}`}
          >
            <span
              className={`inline-block h-3 w-3 transform rounded-full bg-white border border-black transition-transform ${
                enabled ? "translate-x-4" : "translate-x-1"
              }`}
            />
          </button>
          <span className={`text-xs font-mono font-black uppercase tracking-widest w-8 ${enabled ? "text-foreground" : "text-muted-foreground"}`}>
            {DAY_LABELS[day]}
          </span>
        </div>

        {enabled && (
          <button
            type="button"
            onClick={() => onCopyToAll(day)}
            title="Copy these hours to all enabled days"
            className="text-[10px] text-muted-foreground hover:text-orange font-mono font-bold uppercase tracking-wider transition-colors"
          >
            Copy to all
          </button>
        )}
      </div>

      {enabled && (
        <div className="pl-12 space-y-2">
          {slots.map((slot, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <input
                type="time"
                value={slot.start}
                onChange={(e) => onSlotChange(day, idx, "start", e.target.value)}
                className="bg-background border-2 border-border rounded-base p-1 text-xs text-foreground font-mono focus:outline-none focus:border-orange w-28"
              />
              <span className="text-muted-foreground text-xs font-bold">–</span>
              <input
                type="time"
                value={slot.end}
                onChange={(e) => onSlotChange(day, idx, "end", e.target.value)}
                className="bg-background border-2 border-border rounded-base p-1 text-xs text-foreground font-mono focus:outline-none focus:border-orange w-28"
              />
              {slots.length > 1 && (
                <button
                  type="button"
                  onClick={() => onRemoveSlot(day, idx)}
                  className="text-red-400 hover:text-red-300 text-xs font-bold px-1 transition-colors"
                  aria-label="Remove time slot"
                >
                  <X className="size-3.5" aria-hidden="true" />
                </button>
              )}
            </div>
          ))}
          {slots.length < 3 && (
            <button
              type="button"
              onClick={() => onAddSlot(day)}
              className="text-[10px] text-orange font-mono font-bold hover:underline transition-colors"
            >
              + Add time slot
            </button>
          )}
        </div>
      )}

      {!enabled && (
        <div className="pl-12">
          <span className="text-xs text-muted-foreground font-mono italic">Unavailable</span>
        </div>
      )}
    </div>
  );
}

interface AvailabilityGridProps {
  value: string | null; // serialized JSON string (weekly_hours from DB)
  onChange: (json: string) => void;
}

export default function AvailabilityGrid({ value, onChange }: AvailabilityGridProps) {
  const parseValue = useCallback((raw: string | null): WeeklyHoursJson => {
    if (!raw) return {};
    try {
      const parsed = JSON.parse(raw);
      // Handle both object and legacy freetext
      if (typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
      return {};
    } catch {
      return {};
    }
  }, []);

  const [hours, setHours] = useState<WeeklyHoursJson>(() => parseValue(value));

  // Sync when parent value changes (e.g. after fetch)
  useEffect(() => {
    setHours(parseValue(value));
  }, [value, parseValue]);

  const emit = useCallback((next: WeeklyHoursJson) => {
    setHours(next);
    onChange(JSON.stringify(next));
  }, [onChange]);

  const handleToggle = useCallback((day: Day) => {
    setHours((prev) => {
      const next = { ...prev };
      if (next[day] && next[day].length > 0) {
        // Disable: remove
        const { [day]: _, ...rest } = next;
        emit(rest);
        return rest;
      } else {
        // Enable with defaults
        const updated = { ...next, [day]: [{ start: DEFAULT_START, end: DEFAULT_END }] };
        emit(updated);
        return updated;
      }
    });
  }, [emit]);

  const handleSlotChange = useCallback((day: Day, idx: number, field: "start" | "end", val: string) => {
    setHours((prev) => {
      const slots = [...(prev[day] || [])];
      const existing = slots[idx];
      if (!existing) return prev;
      slots[idx] = {
        start: field === "start" ? val : existing.start,
        end: field === "end" ? val : existing.end,
      };
      const next = { ...prev, [day]: slots };
      emit(next);
      return next;
    });
  }, [emit]);

  const handleAddSlot = useCallback((day: Day) => {
    setHours((prev) => {
      const slots = [...(prev[day] || [])];
      slots.push({ start: DEFAULT_START, end: DEFAULT_END });
      const next = { ...prev, [day]: slots };
      emit(next);
      return next;
    });
  }, [emit]);

  const handleRemoveSlot = useCallback((day: Day, idx: number) => {
    setHours((prev) => {
      const slots = (prev[day] || []).filter((_, i) => i !== idx);
      const next = slots.length > 0 ? { ...prev, [day]: slots } : (() => {
        const { [day]: _, ...rest } = prev;
        return rest;
      })();
      emit(next);
      return next;
    });
  }, [emit]);

  const handleCopyToAll = useCallback((sourceDay: Day) => {
    const sourceSlots = hours[sourceDay];
    if (!sourceSlots || sourceSlots.length === 0) return;
    setHours((prev) => {
      const next: WeeklyHoursJson = { ...prev };
      // Only copy to currently enabled days
      for (const day of DAYS) {
        if (day !== sourceDay && next[day] && next[day].length > 0) {
          next[day] = sourceSlots.map((s) => ({ start: s.start, end: s.end }));
        }
      }
      emit(next);
      return next;
    });
  }, [hours, emit]);

  const setPreset = (days: Day[]) => {
    setHours((prev) => {
      const next: WeeklyHoursJson = {};
      for (const d of DAYS) {
        if (days.includes(d)) {
          next[d] = [{ start: DEFAULT_START, end: DEFAULT_END }];
        }
      }
      emit(next);
      return next;
    });
  };

  return (
    <div className="space-y-3">
      {/* Presets */}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest self-center">Quick:</span>
        <button
          type="button"
          onClick={() => setPreset(["monday", "tuesday", "wednesday", "thursday", "friday"])}
          className="px-2.5 py-1 text-[10px] font-black uppercase border-2 border-border bg-muted text-foreground hover:bg-secondary-background rounded transition-colors"
        >
          Weekdays
        </button>
        <button
          type="button"
          onClick={() => setPreset(["saturday", "sunday"])}
          className="px-2.5 py-1 text-[10px] font-black uppercase border-2 border-border bg-muted text-foreground hover:bg-secondary-background rounded transition-colors"
        >
          Weekend
        </button>
        <button
          type="button"
          onClick={() => setPreset([...DAYS])}
          className="px-2.5 py-1 text-[10px] font-black uppercase border-2 border-border bg-muted text-foreground hover:bg-secondary-background rounded transition-colors"
        >
          All Days
        </button>
        <button
          type="button"
          onClick={() => { emit({}); }}
          className="px-2.5 py-1 text-[10px] font-black uppercase border-2 border-border bg-muted text-red-700 hover:bg-red-50 rounded transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Day rows */}
      <div className="space-y-2">
        {DAYS.map((day) => (
          <DayRow
            key={day}
            day={day}
            enabled={!!(hours[day] && hours[day].length > 0)}
            slots={hours[day] || [{ start: DEFAULT_START, end: DEFAULT_END }]}
            onToggle={handleToggle}
            onSlotChange={handleSlotChange}
            onAddSlot={handleAddSlot}
            onRemoveSlot={handleRemoveSlot}
            onCopyToAll={handleCopyToAll}
          />
        ))}
      </div>
    </div>
  );
}
