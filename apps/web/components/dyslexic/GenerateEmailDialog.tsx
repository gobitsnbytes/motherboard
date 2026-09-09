"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Loader2, Sparkles } from "lucide-react";
import {
  DyslexicApiError,
  generateEmail,
  markSent,
  releaseClaim,
  type Contact,
  type EmailDraft,
} from "lib/dyslexic";

/**
 * Draft an email, copy it, then log that it was sent.
 *
 * Dyslexic never sends anything — the volunteer pastes into Gmail and sends
 * from their own mailbox. The button below only records that it happened.
 *
 * Opening this claims the contact, so other volunteers see a draft is underway
 * rather than discovering the collision at send time.
 */
export default function GenerateEmailDialog({
  contact,
  kind,
  onClose,
  onSent,
}: {
  contact: Contact;
  kind: "initial" | "follow_up";
  onClose: () => void;
  onSent: () => void;
}) {
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [tone, setTone] = useState("");
  const [extra, setExtra] = useState("");
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Give the claim back if the volunteer walks away without sending, rather
  // than making everyone else wait out the full window.
  useEffect(() => {
    return () => {
      releaseClaim(contact.id).catch(() => {});
    };
  }, [contact.id]);

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateEmail(contact.id, {
        kind,
        tone: tone || undefined,
        extra_context: extra || undefined,
      });
      setDraft(result);
      setSubject(result.subject);
      setBody(result.body);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not draft the email. You can still write it yourself.",
      );
    } finally {
      setGenerating(false);
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function confirmSent() {
    setSending(true);
    setError(null);
    try {
      await markSent(contact.id, { kind, email_id: draft?.id });
      onSent();
    } catch (err) {
      if (err instanceof DyslexicApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Could not record the send.");
      }
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4">
      <div className="fixed inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />

      <div className="relative z-10 my-8 w-full max-w-2xl rounded-base border-2 border-border bg-secondary-background p-5">
        <h2 className="font-heading text-lg font-bold">
          {kind === "initial" ? "Email" : "Follow up with"} {contact.name}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {contact.role ? `${contact.role} · ` : ""}
          {contact.email ?? "no email on file"}
        </p>

        {!draft && (
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex flex-wrap gap-3">
              <label className="flex-1 text-sm font-medium">
                Tone <span className="text-muted-foreground">(optional)</span>
                <input
                  value={tone}
                  onChange={(event) => setTone(event.target.value)}
                  placeholder="warm, formal, brief…"
                  className="mt-1 w-full rounded-base border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-main"
                />
              </label>
            </div>

            <label className="text-sm font-medium">
              Anything to mention? <span className="text-muted-foreground">(optional)</span>
              <textarea
                value={extra}
                onChange={(event) => setExtra(event.target.value)}
                rows={2}
                placeholder="We're running a 500-person hackathon in March…"
                className="mt-1 w-full rounded-base border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-main"
              />
            </label>

            <button
              type="button"
              onClick={generate}
              disabled={generating}
              className="flex items-center justify-center gap-2 rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-medium text-main-foreground shadow-light transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50"
            >
              {generating ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Writing…
                </>
              ) : (
                <>
                  <Sparkles className="size-4" />
                  Draft the email
                </>
              )}
            </button>
          </div>
        )}

        {(draft || error) && (
          <div className="mt-4 flex flex-col gap-3">
            <label className="text-sm font-medium">
              Subject
              <input
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                className="mt-1 w-full rounded-base border-2 border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-main"
              />
            </label>

            <label className="text-sm font-medium">
              Body
              <textarea
                value={body}
                onChange={(event) => setBody(event.target.value)}
                rows={14}
                className="mt-1 w-full rounded-base border-2 border-border bg-background px-3 py-2 font-mono text-sm leading-relaxed text-foreground focus:outline-none focus:ring-2 focus:ring-main"
              />
            </label>
            <p className="text-xs text-muted-foreground">
              Edit freely — what you copy is what is in the box, not what the model wrote.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-3 rounded-base border-2 border-orange/40 bg-orange/10 px-3 py-2 text-sm text-orange">
            {error}
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-base border-2 border-border px-3 py-2 text-sm font-medium hover:bg-white/5"
          >
            Cancel
          </button>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={copy}
              disabled={!body.trim()}
              className="flex items-center gap-2 rounded-base border-2 border-border px-3 py-2 text-sm font-medium hover:bg-white/5 disabled:opacity-50"
            >
              {copied ? <Check className="size-4 text-green-400" /> : <Copy className="size-4" />}
              {copied ? "Copied" : "Copy for Gmail"}
            </button>

            <button
              type="button"
              onClick={confirmSent}
              disabled={sending}
              className="rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-medium text-main-foreground shadow-light transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50"
            >
              {sending ? "Recording…" : "I've Sent Email"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
