"use client";

import React, { useEffect, useRef, useState } from "react";
import { LoaderCircle, Save, Send, Sparkles, X } from "lucide-react";
import { Button, Input, Label } from "@bnb/ui";
import { api, query, runAssistant, send, type Draft } from "./api";

const STORAGE_KEY = "mailroom.draft";

const EMPTY: Draft = { to: "", cc: "", bcc: "", subject: "", body: "" };

/** Survives a failed send or a closed tab, so nothing typed is ever lost. */
function recover(): Draft | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as Draft) : null;
  } catch {
    return null;
  }
}

function newIdempotencyKey() {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `mailroom-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function Compose({
  account,
  initial,
  onClose,
  onSent,
}: {
  account: string;
  initial: Partial<Draft>;
  onClose: () => void;
  onSent: (messageId: string) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => {
    const recovered = recover();
    return { ...EMPTY, ...(recovered ?? {}), ...initial };
  });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [assistantNote, setAssistantNote] = useState("");
  const [instruction, setInstruction] = useState("");
  const [savedUid, setSavedUid] = useState<string | null>(null);
  const idempotencyKey = useRef(newIdempotencyKey());

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
    } catch {
      // A full or blocked store is not worth interrupting the writer over.
    }
  }, [draft]);

  function update(patch: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...patch }));
  }

  async function run(label: string, work: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await work();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "That did not work");
    } finally {
      setBusy("");
    }
  }

  function saveDraft() {
    void run("save", async () => {
      const result = await api<{ uid: string | null }>(`/drafts${query({ account })}`, {
        method: "POST",
        body: JSON.stringify({ ...draft, replaces_uid: savedUid }),
      });
      setSavedUid(result.uid);
      setAssistantNote("Draft saved to your mailbox.");
    });
  }

  function submit() {
    void run("send", async () => {
      const result = await send(draft, account, idempotencyKey.current);
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // Nothing to clean up.
      }
      idempotencyKey.current = newIdempotencyKey();
      onSent(result.message_id);
    });
  }

  function rewrite() {
    void run("rewrite", async () => {
      const result = await runAssistant(
        { action: "rewrite", instruction, draft: draft.body },
        account,
      );
      if (result.body) {
        update({ body: result.body });
        setAssistantNote("The assistant changed this draft. Read it before sending.");
      }
    });
  }

  return (
    <section
      role="dialog"
      aria-label="Compose message"
      className="fixed inset-0 z-50 flex flex-col bg-background sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[34rem] sm:w-[36rem] sm:rounded-base sm:border-2 sm:border-border sm:shadow-shadow"
    >
      <header className="flex min-h-14 items-center gap-2 border-b-2 border-border bg-background px-4 pt-[env(safe-area-inset-top)] sm:pt-0">
        <h2 className="min-w-0 flex-1 truncate font-heading text-sm font-bold">
          {draft.subject || "New message"}
        </h2>
        <Button
          variant="neutral"
          size="sm"
          className="ml-auto h-11 shrink-0"
          onClick={onClose}
          aria-label="Close compose"
        >
          <X className="size-4" />
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <div className="space-y-3">
          <Field id="compose-to" label="To" value={draft.to} onChange={(to) => update({ to })} />
          <Field id="compose-cc" label="Cc" value={draft.cc} onChange={(cc) => update({ cc })} />
          <Field
            id="compose-subject"
            label="Subject"
            value={draft.subject}
            onChange={(subject) => update({ subject })}
          />
        </div>

        <Label htmlFor="compose-body" className="sr-only">
          Message
        </Label>
        <textarea
          id="compose-body"
          value={draft.body}
          onChange={(event) => update({ body: event.target.value })}
          placeholder="Write your message"
          className="mt-4 min-h-56 w-full resize-y rounded-base border-2 border-border bg-background px-3 py-2 text-[15px] leading-7 outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring"
        />

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Input
            aria-label="Instruction for the assistant"
            placeholder="Tell the assistant what to change"
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            className="h-11 min-w-48 flex-1"
          />
          <Button
            variant="neutral"
            className="h-11 gap-2"
            disabled={Boolean(busy)}
            onClick={rewrite}
          >
            {busy === "rewrite" ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            Rewrite
          </Button>
        </div>

        {assistantNote && <p className="mt-3 text-sm text-muted-foreground">{assistantNote}</p>}
        {error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {error} Your text is kept here until it sends.
          </p>
        )}
      </div>

      <footer className="flex min-h-16 flex-wrap items-center gap-2 border-t-2 border-border px-4 pb-[env(safe-area-inset-bottom)] sm:pb-0">
        <Button className="h-11 gap-2" disabled={Boolean(busy)} onClick={submit}>
          {busy === "send" ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
          Send
        </Button>
        <Button variant="neutral" className="h-11 gap-2" disabled={Boolean(busy)} onClick={saveDraft}>
          {busy === "save" ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
          Save draft
        </Button>
      </footer>
    </section>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex min-h-11 items-center gap-3 border-b-2 border-border pb-2">
      <Label htmlFor={id} className="w-14 shrink-0 text-xs text-muted-foreground">
        {label}
      </Label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
    </div>
  );
}
