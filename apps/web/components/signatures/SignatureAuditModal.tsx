"use client";

import React, { useEffect, useState } from "react";
import { ScrollText, Loader2, ShieldCheck, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@bnb/ui";

interface AuditEntry {
  id: string;
  action: string;
  ip_address?: string | null;
  user_agent?: string | null;
  details?: string | null;
  created_at: string;
}

interface AuditTrail {
  request_id: string;
  title: string;
  status: string;
  document_hash?: string | null;
  entries: AuditEntry[];
}

export default function SignatureAuditModal({
  requestId,
  onClose,
}: {
  requestId: string | null;
  onClose: () => void;
}) {
  const [trail, setTrail] = useState<AuditTrail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!requestId) {
      setTrail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/signatures/requests/${requestId}/audit`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load audit trail.");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setTrail(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the audit trail.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  if (!requestId) return null;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto p-0">
        <div className="flex items-start justify-between border-b-2 border-border bg-main p-4 text-main-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-heading text-base font-black uppercase tracking-wide">
              <ScrollText className="size-4" /> Signature Audit Trail
            </DialogTitle>
            {trail && (
              <p className="text-[11px] text-muted-foreground">{trail.title}</p>
            )}
          </DialogHeader>
          <DialogClose asChild>
            <button
              aria-label="Close"
              className="rounded-base border-2 border-border bg-blank p-1 text-main-foreground transition-all hover:translate-x-[1px] hover:translate-y-[1px]"
            >
              <X className="size-4" />
            </button>
          </DialogClose>
        </div>

        <div className="space-y-4 p-4">
          {error && (
            <div role="alert" className="rounded-base border-2 border-border bg-blank p-3 text-xs font-bold text-main-foreground">
              {error}
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center gap-2 py-8 text-sm font-bold text-muted-foreground">
              <Loader2 className="size-5 animate-spin" /> Loading audit events…
            </div>
          )}

          {trail && (
            <>
              <div className="rounded-base border-2 border-border bg-blank p-3">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
                  <span className="font-black uppercase tracking-wider text-main-foreground">
                    Status: {trail.status}
                  </span>
                  {trail.document_hash && (
                    <span className="font-mono text-[10px] text-muted-foreground break-all">
                      SHA-256: {trail.document_hash}
                    </span>
                  )}
                </div>
                <p className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
                  <ShieldCheck className="size-3" />
                  Tamper-evident trail — IT Act §10A / BSA §63B evidentiary record.
                </p>
              </div>

              <ol className="relative space-y-3 border-l-2 border-border pl-4">
                {[...trail.entries].reverse().map((e) => (
                  <li key={e.id} className="relative">
                    <span className="absolute -left-[22px] top-1 size-2.5 rounded-none border-2 border-border bg-main" aria-hidden />
                    <div className="rounded-base border-2 border-border bg-background p-2.5 shadow-shadow">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-black uppercase tracking-wide text-main-foreground">
                          {e.action.replace(/_/g, " ")}
                        </span>
                        <time className="text-[10px] text-muted-foreground">
                          {new Date(e.created_at).toLocaleString()}
                        </time>
                      </div>
                      {e.details && (
                        <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{e.details}</p>
                      )}
                      {e.ip_address && e.ip_address !== "internal" && (
                        <p className="mt-1 font-mono text-[10px] text-muted-foreground">IP {e.ip_address}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
