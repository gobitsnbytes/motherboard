"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type DyslexicEvent = {
  type: string;
  payload: Record<string, unknown>;
};

export type StreamStatus = "connecting" | "live" | "degraded";

const EVENT_TYPES = [
  "dyslexic.company.created",
  "dyslexic.company.updated",
  "dyslexic.research.completed",
  "dyslexic.contact.created",
  "dyslexic.contact.updated",
  "dyslexic.contact.claimed",
  "dyslexic.contact.released",
  "dyslexic.email.sent",
  "dyslexic.outcome.recorded",
  "dyslexic.follow_up.resolved",
] as const;

const MAX_RECONNECT_ATTEMPTS = 3;
const POLL_INTERVAL_MS = 30_000;

/**
 * Subscribe to live Dyslexic changes.
 *
 * Correctness never depends on this — the duplicate-outreach guard lives in the
 * database, so the stream only decides how soon you find out. After a few failed
 * reconnects it gives up and falls back to polling, reporting "degraded" so the
 * UI can say so rather than silently going stale.
 *
 * @param onChange Called for each event, and on each poll tick when degraded.
 *                 Keep it stable (useCallback) or the stream will reconnect.
 */
export function useDyslexicStream(onChange: (event: DyslexicEvent | null) => void) {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const handlerRef = useRef(onChange);
  const attemptsRef = useRef(0);

  // Keep the latest callback without making it a reconnect trigger.
  useEffect(() => {
    handlerRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    const startPolling = () => {
      if (pollTimer) return;
      setStatus("degraded");
      pollTimer = setInterval(() => handlerRef.current(null), POLL_INTERVAL_MS);
    };

    const connect = () => {
      if (cancelled) return;

      source = new EventSource("/api/dyslexic/stream");

      source.addEventListener("connected", () => {
        attemptsRef.current = 0;
        if (pollTimer) {
          clearInterval(pollTimer);
          pollTimer = null;
        }
        setStatus("live");
      });

      for (const type of EVENT_TYPES) {
        source.addEventListener(type, (raw) => {
          try {
            const payload = JSON.parse((raw as MessageEvent).data ?? "{}");
            handlerRef.current({ type, payload });
          } catch {
            // A malformed frame shouldn't kill the stream; refetch anyway.
            handlerRef.current(null);
          }
        });
      }

      source.onerror = () => {
        source?.close();
        source = null;
        if (cancelled) return;

        attemptsRef.current += 1;
        if (attemptsRef.current > MAX_RECONNECT_ATTEMPTS) {
          startPolling();
          return;
        }

        setStatus("connecting");
        // Back off so a restarting API doesn't get hammered by every open tab.
        const delay = Math.min(1000 * 2 ** (attemptsRef.current - 1), 8000);
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      source?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pollTimer) clearInterval(pollTimer);
    };
  }, []);

  return { status };
}

/**
 * Re-run a loader when anything changes.
 *
 * The common case: a page loads a list, then wants it refreshed whenever
 * someone else touches the data.
 */
export function useDyslexicRefresh(reload: () => void) {
  const stable = useCallback(() => reload(), [reload]);
  return useDyslexicStream(stable);
}
