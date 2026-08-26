"use client";

import React, { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  CheckCircle2,
  Circle,
  ArrowRightCircle,
  Archive,
  ArchiveRestore,
  Ban,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@bnb/ui";

interface ChecklistStep {
  key: string;
  label: string;
  completed: boolean;
  completed_at: string | null;
  completed_by: string | null;
}

export interface ForkOnboardingDetailData {
  fork_id: string;
  city_name: string;
  slug: string;
  stage: string;
  checklist: ChecklistStep[];
  next_stage: string | null;
  next_stage_blockers: string[];
  health_score: number;
  overall_status: string;
  remedies: string[];
}

interface Props {
  forkId: string | null;
  onClose: () => void;
  onChanged?: () => void;
}

const STAGE_STYLES: Record<string, string> = {
  approved: "bg-[#97192C] text-white",
  archived: "bg-[#413F3B] text-white",
  compliance_check: "bg-[#FC920D] text-[#120F0A]",
  in_review: "bg-[#FC920D] text-[#120F0A]",
  submitted: "bg-[#FEE9CF] text-[#120F0A]",
};

async function fetchDetail(forkId: string): Promise<ForkOnboardingDetailData> {
  const res = await fetch(`/api/forks/${forkId}/onboarding`);
  if (!res.ok) throw new Error("Failed to load onboarding state.");
  return res.json();
}

export default function ForkOnboardingModal({ forkId, onClose, onChanged }: Props) {
  const [detail, setDetail] = useState<ForkOnboardingDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [reasonMode, setReasonMode] = useState<"reject" | "archive" | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await fetchDetail(id));
    } catch {
      setError("Could not load onboarding state.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (forkId) {
      setReason("");
      setReasonMode(null);
      void load(forkId);
    } else {
      setDetail(null);
    }
  }, [forkId, load]);

  if (!forkId) return null;

  const toggleStep = async (stepKey: string, completed: boolean) => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/forks/${detail.fork_id}/onboarding/checklist/${stepKey}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ completed }),
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : "Update failed.");
      }
      setDetail(await res.json());
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setBusy(false);
    }
  };

  const runAction = async (action: "advance" | "reject" | "archive" | "reactivate") => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/forks/${detail.fork_id}/onboarding/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          reason: action === "reject" || action === "archive" ? reason || undefined : undefined,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : `${action} failed.`);
      }
      setDetail(await res.json());
      setReason("");
      setReasonMode(null);
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed.`);
    } finally {
      setBusy(false);
    }
  };

  const canAdvance =
    detail?.stage &&
    !["approved", "archived"].includes(detail.stage) &&
    (detail.next_stage_blockers?.length ?? 0) === 0;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto p-0">
        <AnimatePresence mode="wait">
            {loading || !detail ? (
              <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="flex items-center justify-center gap-2 p-10 text-sm font-bold text-main-foreground">
                <Loader2 className="size-5 animate-spin" /> Loading onboarding state…
              </motion.div>
            ) : (
              <motion.div key="body" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                {/* Header */}
                <div className="flex items-start justify-between border-b-2 border-border bg-burgundy p-4 text-white">
                  <DialogHeader>
                    <DialogTitle className="font-heading text-lg font-black uppercase tracking-wide">
                      {detail.city_name}
                    </DialogTitle>
                    <div className="mt-1 flex items-center gap-2">
                      <span className={`border-2 border-border px-2 py-0.5 text-[10px] font-black uppercase ${STAGE_STYLES[detail.stage] ?? "bg-blank text-main-foreground"}`}>
                        {detail.stage.replace("_", " ")}
                      </span>
                      <span className="text-[10px] font-mono opacity-80">/{detail.slug}</span>
                    </div>
                  </DialogHeader>
                  <DialogClose asChild>
                    <button aria-label="Close" className="rounded-base border-2 border-border bg-blank p-1 text-main-foreground transition-all hover:translate-x-[1px] hover:translate-y-[1px]">
                      <X className="size-4" />
                    </button>
                  </DialogClose>
                </div>

                <div className="space-y-4 p-4">
                  {error && (
                    <div role="alert" className="flex items-start gap-2 rounded-base border-2 border-[#97192C] bg-[#97192C]/10 p-2.5 text-xs font-bold text-[#97192C]">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  {/* Blockers */}
                  {detail.next_stage_blockers.length > 0 && (
                    <div className="rounded-base border-2 border-border bg-blank p-3">
                      <p className="mb-1.5 text-[10px] font-black uppercase tracking-wider text-main-foreground">
                        Blockers to {detail.next_stage?.replace("_", " ")}
                      </p>
                      <ul className="list-inside list-disc space-y-0.5 text-[11px] text-muted-foreground">
                        {detail.next_stage_blockers.map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Checklist */}
                  <div className="rounded-base border-2 border-border bg-blank">
                    <p className="border-b-2 border-border p-2.5 text-[10px] font-black uppercase tracking-wider text-main-foreground">
                      Onboarding Checklist &middot; NGC &sect;4.1
                    </p>
                    <ul className="divide-y-2 divide-border">
                      {detail.checklist.map((step) => (
                        <li key={step.key}>
                          <button
                            disabled={busy}
                            onClick={() => toggleStep(step.key, !step.completed)}
                            className="flex w-full items-center gap-2.5 p-2.5 text-left transition-colors hover:bg-blank disabled:opacity-60"
                          >
                            {step.completed ? (
                              <CheckCircle2 className="size-4 shrink-0 text-[#1f8b4c]" />
                            ) : (
                              <Circle className="size-4 shrink-0 text-muted-foreground" />
                            )}
                            <span className={`text-xs ${step.completed ? "text-muted-foreground line-through" : "font-bold text-main-foreground"}`}>
                              {step.label}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Actions */}
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      {detail.stage === "archived" ? (
                        <button
                          disabled={busy}
                          onClick={() => runAction("reactivate")}
                          className="col-span-2 flex items-center justify-center gap-1.5 rounded-base border-2 border-border bg-main px-3 py-2 text-xs font-black uppercase text-main-foreground shadow-shadow transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-60"
                        >
                          <ArchiveRestore className="size-4" /> Reactivate Fork
                        </button>
                      ) : (
                        <>
                          <button
                            disabled={busy || !canAdvance}
                            title={canAdvance ? "" : "Resolve blockers first"}
                            onClick={() => runAction("advance")}
                            className="col-span-2 flex items-center justify-center gap-1.5 rounded-base border-2 border-border bg-main px-3 py-2 text-xs font-black uppercase text-main-foreground shadow-shadow transition-all enabled:hover:translate-x-[2px] enabled:hover:translate-y-[2px] enabled:hover:shadow-none disabled:opacity-40"
                          >
                            {busy ? <Loader2 className="size-4 animate-spin" /> : <ArrowRightCircle className="size-4" />}
                            Advance to {detail.next_stage?.replace("_", " ") ?? "—"}
                          </button>
                          {detail.stage !== "approved" && (
                            <button
                              disabled={busy}
                              onClick={() => { setReasonMode(reasonMode === "reject" ? null : "reject"); }}
                              className="flex items-center justify-center gap-1.5 rounded-base border-2 border-border bg-blank px-3 py-2 text-xs font-black uppercase text-main-foreground shadow-shadow transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none"
                            >
                              <Ban className="size-4" /> Reject
                            </button>
                          )}
                          <button
                            disabled={busy}
                            onClick={() => { setReasonMode(reasonMode === "archive" ? null : "archive"); }}
                            className="flex items-center justify-center gap-1.5 rounded-base border-2 border-border bg-blank px-3 py-2 text-xs font-black uppercase text-main-foreground shadow-shadow transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none"
                          >
                            <Archive className="size-4" /> Archive
                          </button>
                        </>
                      )}
                    </div>

                    {reasonMode && (
                      <div className="space-y-2 rounded-base border-2 border-border bg-blank p-2.5">
                        <label htmlFor="fork-action-reason" className="block text-[10px] font-black uppercase tracking-wider text-main-foreground">
                          Reason ({reasonMode}) — required, recorded in audit log
                        </label>
                        <textarea
                          id="fork-action-reason"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          rows={2}
                          className="w-full rounded-base border-2 border-border bg-background p-2 text-xs text-main-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          placeholder="e.g. No active teen leadership."
                        />
                        <button
                          disabled={busy || !reason.trim()}
                          onClick={() => runAction(reasonMode)}
                          className="w-full rounded-base border-2 border-border bg-[#97192C] px-3 py-1.5 text-xs font-black uppercase text-white shadow-shadow transition-all enabled:hover:translate-x-[2px] enabled:hover:translate-y-[2px] enabled:hover:shadow-none disabled:opacity-40"
                        >
                          Confirm {reasonMode}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  );
}
