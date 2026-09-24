"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

type RouteErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
  segment: string;
};

export function RouteError({ error, reset, segment }: RouteErrorProps) {
  useEffect(() => {
    // Errors with a digest came from server rendering and were already
    // reported by onRequestError; the client copy is a redacted duplicate.
    if (error.digest) return;
    Sentry.captureException(error, { tags: { "route.segment": segment, boundary: "route" } });
  }, [error, segment]);

  return (
    <main className="flex min-h-[60vh] w-full flex-col items-center justify-center px-6 text-center text-[#120f0a]">
      <p className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-[#97192c]">Motherboard / error</p>
      <h1 className="mt-5 font-serif text-5xl leading-none">Something broke</h1>
      <p className="mt-5 max-w-sm text-base leading-7 text-[#120f0a]/65">
        This page failed to load. Try again, and if it keeps happening, share the reference below with an admin.
      </p>
      {error.digest ? <p className="mt-3 font-mono text-xs text-[#120f0a]/50">Reference {error.digest}</p> : null}
      <button
        type="button"
        onClick={reset}
        className="mt-8 border-2 border-[#120f0a] bg-[#fc920d] px-5 py-3 font-mono text-xs font-bold uppercase tracking-[0.14em] shadow-[4px_4px_0_#120f0a] transition-transform hover:translate-x-1 hover:translate-y-1 hover:shadow-none"
      >
        Try again
      </button>
    </main>
  );
}
