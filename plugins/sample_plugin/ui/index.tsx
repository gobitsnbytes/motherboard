"use client";

import React, { useEffect, useState } from "react";
import { Puzzle, RefreshCw, CheckCircle2 } from "lucide-react";

export default function SamplePluginUI() {
  const [data, setData] = useState<{ message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGreeting = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/plugins/sample_plugin/hello");
      if (!res.ok) {
        throw new Error(`Failed to fetch from plugin API: ${res.status}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGreeting();
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6 border-4 border-border bg-main/5 rounded-base">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center p-2.5 border-2 border-border bg-main rounded-base text-main-foreground shadow-light">
            <Puzzle className="size-6" />
          </div>
          <div>
            <h2 className="text-xl font-heading font-bold text-foreground">
              Dynamic Sample Plugin
            </h2>
            <p className="text-xs text-muted-foreground font-base mt-0.5">
              This interface is loaded on-the-fly via the Next.js Dynamic Plugin Mounting Router.
            </p>
          </div>
        </div>

        <button
          onClick={fetchGreeting}
          disabled={loading}
          className="flex items-center gap-2 border-2 border-border bg-main text-main-foreground px-4 py-2 text-sm font-bold rounded-base hover:bg-main/90 transition-all hover:translate-x-[2px] hover:translate-y-[2px] active:translate-x-0 active:translate-y-0"
        >
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
          Reload
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Core Status Card */}
        <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light">
          <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider mb-3">
            API Connectivity
          </h3>
          {loading ? (
            <div className="h-10 animate-pulse bg-main/15 rounded-base" />
          ) : error ? (
            <div className="border-2 border-border bg-red-500/10 p-3 rounded-base text-xs font-bold text-red-500">
              {error}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 text-sm font-bold text-foreground">
                <CheckCircle2 className="size-4 text-green-500" />
                Response Status: 200 OK
              </div>
              <div className="bg-main/10 border-2 border-border p-3 rounded-base text-xs font-mono text-foreground font-medium">
                {data?.message}
              </div>
            </div>
          )}
        </div>

        {/* Plugin Metadata Card */}
        <div className="border-4 border-border bg-bg p-5 rounded-base shadow-light">
          <h3 className="text-sm font-heading font-bold text-foreground uppercase tracking-wider mb-3">
            Plugin Registration Metadata
          </h3>
          <div className="flex flex-col gap-2.5 text-xs text-foreground font-base font-semibold">
            <div className="flex justify-between border-b-2 border-border pb-1.5">
              <span className="text-muted-foreground">Plugin ID</span>
              <span>sample_plugin</span>
            </div>
            <div className="flex justify-between border-b-2 border-border pb-1.5">
              <span className="text-muted-foreground">Version</span>
              <span>0.1.0</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Lifecycle Status</span>
              <span className="text-green-500 font-bold">ACTIVE & INSTALLED</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
