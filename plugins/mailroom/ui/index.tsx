"use client";

import React, { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  FileText,
  ImageOff,
  Inbox,
  LogOut,
  Mail,
  Paperclip,
  PenLine,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  Sparkles,
  Star,
  Trash2,
} from "lucide-react";
import { Button, Input, Label, Skeleton } from "@bnb/ui";
import Login from "./login";
import Compose from "./compose";
import {
  api,
  attachmentUrl,
  friendlyDate,
  fullDate,
  MailAuthError,
  query,
  rawUrl,
  readableSize,
  runAssistant,
  type AiPreferences,
  type Draft,
  type Folder,
  type MailMessage,
  type MessageList,
  type Session,
} from "./api";

const PAGE_SIZE = 40;

export default function MailroomUI() {
  const [session, setSession] = useState<Session | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folder, setFolder] = useState("INBOX");
  const [list, setList] = useState<MessageList | null>(null);
  const [offset, setOffset] = useState(0);
  const [term, setTerm] = useState("");
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<MailMessage | null>(null);
  const [account, setAccount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [composing, setComposing] = useState<Partial<Draft> | null>(null);
  const [allowRemote, setAllowRemote] = useState(false);
  const [plainOnly, setPlainOnly] = useState(false);
  const [assistant, setAssistant] = useState("");
  const [showPreferences, setShowPreferences] = useState(false);

  const handle = useCallback((reason: unknown, fallback: string) => {
    if (reason instanceof MailAuthError) {
      setSession((current) => (current ? { ...current, authenticated: false } : current));
      setError("Your mail password stopped working. Sign in again.");
      return;
    }
    setError(reason instanceof Error ? reason.message : fallback);
  }, []);

  useEffect(() => {
    let active = true;
    api<Session>("/session")
      .then((value) => active && setSession(value))
      .catch((reason) => active && handle(reason, "Mailroom is unavailable"));
    return () => {
      active = false;
    };
  }, [handle]);

  useEffect(() => {
    if (session?.authenticated && session.email) setAccount(session.email);
  }, [session?.authenticated, session?.email]);

  const loadFolders = useCallback(async () => {
    if (!account) return;
    try {
      setFolders(await api<Folder[]>(`/folders${query({ account })}`));
    } catch (reason) {
      handle(reason, "Folders are unavailable");
    }
  }, [account, handle]);

  const loadList = useCallback(async () => {
    if (!account) return;
    setBusy(true);
    setError("");
    try {
      const path = searching
        ? `/search${query({ account, folder, q: term, limit: PAGE_SIZE })}`
        : `/messages${query({ account, folder, limit: PAGE_SIZE, offset })}`;
      setList(await api<MessageList>(path));
    } catch (reason) {
      handle(reason, "That folder is unavailable");
    } finally {
      setBusy(false);
    }
  }, [account, folder, offset, searching, term, handle]);

  useEffect(() => {
    void loadFolders();
  }, [loadFolders]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const openMessage = useCallback(
    async (summary: { uid: string; folder: string; unread: boolean }, remote = false) => {
      setBusy(true);
      setError("");
      setAssistant("");
      setPlainOnly(false);
      setAllowRemote(remote);
      try {
        const message = await api<MailMessage>(
          `/messages/${summary.uid}${query({
            account,
            folder: summary.folder,
            remote_images: remote,
          })}`,
        );
        setSelected(message);
        if (summary.unread) {
          await api(`/messages/${summary.uid}/flags${query({ account, folder: summary.folder })}`, {
            method: "POST",
            body: JSON.stringify({ seen: true }),
          });
          setList((current) =>
            current
              ? {
                  ...current,
                  messages: current.messages.map((row) =>
                    row.uid === summary.uid ? { ...row, unread: false } : row,
                  ),
                }
              : current,
          );
          void loadFolders();
        }
      } catch (reason) {
        handle(reason, "That message is unavailable");
      } finally {
        setBusy(false);
      }
    },
    [account, handle, loadFolders],
  );

  // Lightweight triage: only when the reader has asked for it, and only ever a
  // suggestion. Nothing is archived or sent without them acting on it.
  useEffect(() => {
    if (!selected || !session?.preferences.auto_triage) return;
    let active = true;
    runAssistant({ action: "triage", folder: selected.folder, uid: selected.uid }, account)
      .then((result) => {
        if (active) {
          setAssistant(`Suggested: ${result.suggestion ?? "keep"}. ${result.reason ?? ""}`.trim());
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [selected, session?.preferences.auto_triage, account]);

  async function act(path: string, init: RequestInit, note: string) {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await api(path, init);
      setSelected(null);
      setAssistant(note);
      await loadList();
      void loadFolders();
    } catch (reason) {
      handle(reason, "That action did not work");
    } finally {
      setBusy(false);
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearching(term.trim().length > 1);
  }

  async function ask(action: "summarize" | "triage") {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await runAssistant(
        { action, folder: selected.folder, uid: selected.uid },
        account,
      );
      setAssistant(
        action === "summarize"
          ? result.summary ?? "The assistant had nothing to add."
          : `Suggested: ${result.suggestion ?? "keep"}. ${result.reason ?? ""}`.trim(),
      );
    } catch (reason) {
      handle(reason, "The assistant is unavailable");
    } finally {
      setBusy(false);
    }
  }

  async function draftReply() {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await runAssistant(
        { action: "reply", folder: selected.folder, uid: selected.uid },
        account,
      );
      setComposing(replyDraft(selected, result.body ?? ""));
    } catch (reason) {
      handle(reason, "The assistant is unavailable");
    } finally {
      setBusy(false);
    }
  }

  const unreadInbox = useMemo(
    () => folders.find((entry) => entry.role === "inbox")?.unread ?? 0,
    [folders],
  );

  if (!session) return <MailroomLoading />;
  if (!session.authenticated) return <Login onSignedIn={setSession} />;

  return (
    <section className="min-h-[calc(100dvh-9rem)] overflow-hidden rounded-2xl border border-border bg-background text-foreground">
      <header className="flex min-h-16 items-center gap-3 border-b border-border px-4 sm:px-5">
        <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Mail className="size-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h1 className="text-base font-semibold leading-tight">
            Mailroom
            {unreadInbox > 0 && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {unreadInbox} unread
              </span>
            )}
          </h1>
          {session.accounts.length > 1 ? (
            <select
              value={account}
              onChange={(event) => {
                setSelected(null);
                setList(null);
                setOffset(0);
                setFolder("INBOX");
                setAccount(event.target.value);
              }}
              className="max-w-56 bg-transparent text-sm text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Active mailbox"
            >
              {session.accounts.map((entry) => (
                <option key={entry} value={entry}>
                  {entry}
                </option>
              ))}
            </select>
          ) : (
            <p className="truncate text-sm text-muted-foreground">{account}</p>
          )}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="neutral"
            size="sm"
            className="h-10"
            disabled={busy}
            onClick={() => void loadList()}
            aria-label="Refresh"
          >
            <RefreshCw className={`size-4 ${busy ? "animate-spin" : ""}`} />
          </Button>
          <Button
            variant="neutral"
            size="sm"
            className="h-10"
            onClick={() => setShowPreferences((value) => !value)}
            aria-expanded={showPreferences}
            aria-label="Writing preferences"
          >
            <SlidersHorizontal className="size-4" />
          </Button>
          <Button
            variant="neutral"
            size="sm"
            className="h-10"
            onClick={async () => {
              setSession(await api<Session>("/session", { method: "DELETE" }));
              setList(null);
              setSelected(null);
              setFolders([]);
            }}
            aria-label="Sign out of Mailroom"
          >
            <LogOut className="size-4" />
          </Button>
        </div>
      </header>

      {error && (
        <p
          role="alert"
          className="flex items-center gap-3 border-b border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
          <button
            type="button"
            onClick={() => void loadList()}
            className="ml-auto min-h-11 underline underline-offset-4"
          >
            Retry
          </button>
        </p>
      )}

      {showPreferences && (
        <Preferences
          value={session.preferences}
          onSave={(preferences) => {
            setSession({ ...session, preferences });
            setShowPreferences(false);
          }}
          onError={(reason) => handle(reason, "Preferences could not be saved")}
        />
      )}

      <div className="grid min-h-[calc(100dvh-13rem)] md:grid-cols-[13rem_minmax(18rem,25rem)_1fr]">
        <nav
          className="hidden border-r border-border p-3 md:block"
          aria-label="Mail folders"
        >
          <Button
            className="mb-4 h-11 w-full justify-start gap-2"
            onClick={() => setComposing({})}
          >
            <PenLine className="size-4" />
            Compose
          </Button>
          {folders.map((entry) => (
            <button
              key={entry.name}
              type="button"
              aria-current={entry.name === folder}
              onClick={() => {
                setFolder(entry.name);
                setOffset(0);
                setSearching(false);
                setSelected(null);
              }}
              className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                entry.name === folder ? "bg-muted font-medium" : "hover:bg-muted/60"
              }`}
            >
              {entry.role === "inbox" ? (
                <Inbox className="size-4 shrink-0" />
              ) : (
                <Mail className="size-4 shrink-0" />
              )}
              <span className="truncate">{entry.display_name}</span>
              {entry.unread > 0 && (
                <span className="ml-auto tabular-nums text-xs text-muted-foreground">
                  {entry.unread}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className={`${selected ? "hidden md:block" : "block"} border-r border-border`}>
          <form onSubmit={submitSearch} className="flex h-14 items-center gap-2 border-b border-border px-3">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <Input
              aria-label="Search this folder"
              placeholder="Search this folder"
              value={term}
              onChange={(event) => {
                setTerm(event.target.value);
                if (!event.target.value) setSearching(false);
              }}
              className="h-10 border-0 bg-transparent px-0 focus-visible:ring-0"
            />
          </form>

          <div className="max-h-[calc(100dvh-20rem)] overflow-y-auto">
            {busy && !list ? <MessageListLoading /> : null}
            {list?.messages.length === 0 ? (
              <p className="p-8 text-center text-sm text-muted-foreground">
                {searching ? "Nothing matched that search." : "This folder is empty."}
              </p>
            ) : null}
            {list?.messages.map((message) => (
              <button
                key={message.uid}
                type="button"
                onClick={() => void openMessage(message)}
                aria-current={selected?.uid === message.uid}
                className={`block min-h-24 w-full border-b border-border px-4 py-3 text-left transition-colors duration-150 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset ${
                  selected?.uid === message.uid ? "bg-muted/60" : ""
                }`}
              >
                <span className="flex items-baseline gap-3">
                  <span
                    className={`min-w-0 flex-1 truncate text-sm ${
                      message.unread ? "font-semibold" : "font-medium"
                    }`}
                  >
                    {message.sender}
                  </span>
                  {message.flagged && (
                    <Star className="size-3.5 shrink-0 fill-primary text-primary" aria-label="Flagged" />
                  )}
                  {message.has_attachments && (
                    <Paperclip className="size-3.5 shrink-0 text-muted-foreground" aria-label="Has attachments" />
                  )}
                  <time className="shrink-0 text-xs text-muted-foreground" dateTime={message.date ?? undefined}>
                    {friendlyDate(message.date)}
                  </time>
                </span>
                <span className={`mt-1 block truncate text-sm ${message.unread ? "font-semibold" : ""}`}>
                  {message.subject}
                </span>
                <span className="mt-1 block truncate text-sm text-muted-foreground">
                  {message.snippet || "No preview"}
                </span>
              </button>
            ))}
          </div>

          {!searching && list && list.total > PAGE_SIZE && (
            <div className="flex min-h-14 items-center justify-between border-t border-border px-3 text-sm">
              <Button
                variant="neutral"
                size="sm"
                className="h-11"
                disabled={offset === 0 || busy}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                <ChevronLeft className="size-4" /> Newer
              </Button>
              <span className="tabular-nums text-muted-foreground">
                {offset + 1}&ndash;{Math.min(offset + PAGE_SIZE, list.total)} of {list.total}
              </span>
              <Button
                variant="neutral"
                size="sm"
                className="h-11"
                disabled={offset + PAGE_SIZE >= list.total || busy}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Older <ChevronRight className="size-4" />
              </Button>
            </div>
          )}
        </div>

        <main className={`${selected ? "block" : "hidden md:flex"} min-w-0 flex-col`}>
          {selected ? (
            <article>
              <div className="flex min-h-14 flex-wrap items-center gap-1 border-b border-border px-3 md:px-5">
                <Button
                  variant="neutral"
                  size="sm"
                  className="mr-1 h-11 md:hidden"
                  onClick={() => setSelected(null)}
                  aria-label="Back to the message list"
                >
                  <ArrowLeft className="size-4" />
                </Button>
                <Button
                  variant="neutral"
                  size="sm"
                  className="h-11"
                  disabled={busy}
                  onClick={() =>
                    void act(
                      `/messages/${selected.uid}/archive${query({ account, folder: selected.folder })}`,
                      { method: "POST" },
                      "Archived.",
                    )
                  }
                >
                  <Archive className="size-4" /> Archive
                </Button>
                <Button
                  variant="neutral"
                  size="sm"
                  className="h-11"
                  disabled={busy}
                  onClick={() =>
                    void act(
                      `/messages/${selected.uid}${query({ account, folder: selected.folder })}`,
                      { method: "DELETE" },
                      "Moved to Trash.",
                    )
                  }
                >
                  <Trash2 className="size-4" /> Delete
                </Button>
                <Button
                  variant="neutral"
                  size="sm"
                  className="h-11"
                  disabled={busy}
                  onClick={() => void ask("summarize")}
                >
                  <Sparkles className="size-4" /> Summarize
                </Button>
                <Button
                  variant="neutral"
                  size="sm"
                  className="h-11"
                  disabled={busy}
                  onClick={() => void ask("triage")}
                >
                  Triage
                </Button>
                <Button
                  size="sm"
                  className="ml-auto h-11 gap-2"
                  onClick={() => setComposing(replyDraft(selected, ""))}
                >
                  <Send className="size-4" /> Reply
                </Button>
                <Button
                  variant="neutral"
                  size="sm"
                  className="h-11 gap-2"
                  disabled={busy}
                  onClick={() => void draftReply()}
                >
                  <Sparkles className="size-4" /> Draft reply
                </Button>
              </div>

              {assistant && (
                <p className="border-b border-border bg-muted/40 px-5 py-3 text-sm sm:px-8">
                  {assistant}
                </p>
              )}

              <div className="mx-auto max-w-3xl px-5 py-7 sm:px-8">
                <h2 className="text-2xl font-semibold tracking-tight">{selected.subject}</h2>
                <div className="mt-5 border-b border-border pb-5 text-sm">
                  <p className="font-medium">{selected.sender}</p>
                  <p className="mt-1 text-muted-foreground">to {selected.to}</p>
                  {selected.cc && <p className="text-muted-foreground">cc {selected.cc}</p>}
                  <p className="mt-1 text-xs text-muted-foreground">{fullDate(selected.date)}</p>
                </div>

                {selected.remote_images_blocked > 0 && !allowRemote && (
                  <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm">
                    <ImageOff className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span>
                      {selected.remote_images_blocked} remote image
                      {selected.remote_images_blocked === 1 ? "" : "s"} blocked.
                    </span>
                    <Button
                      variant="neutral"
                      size="sm"
                      className="ml-auto h-11"
                      onClick={() =>
                        void openMessage(
                          { uid: selected.uid, folder: selected.folder, unread: false },
                          true,
                        )
                      }
                    >
                      Load images
                    </Button>
                  </div>
                )}

                {selected.html && (
                  <div className="mt-5 flex items-center gap-3 text-sm">
                    <button
                      type="button"
                      onClick={() => setPlainOnly((value) => !value)}
                      className="min-h-11 underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {plainOnly ? "Show formatted message" : "Show plain text instead"}
                    </button>
                    <a
                      href={rawUrl(selected, account)}
                      className="ml-auto min-h-11 text-muted-foreground underline underline-offset-4"
                    >
                      Download original
                    </a>
                  </div>
                )}

                {selected.html && !plainOnly ? (
                  <div
                    className="mailroom-body mt-6 overflow-x-auto text-[15px] leading-7"
                    // Sanitized on the server with an allowlist: scripts, styles,
                    // forms, remote embeds, and escaping CSS are removed there.
                    dangerouslySetInnerHTML={{ __html: selected.html }}
                  />
                ) : (
                  <pre className="mt-6 whitespace-pre-wrap break-words font-sans text-[15px] leading-7">
                    {selected.text || "This message has no plain text body."}
                  </pre>
                )}

                {selected.links.length > 0 && !plainOnly && (
                  <details className="mt-7 text-sm">
                    <summary className="min-h-11 cursor-pointer text-muted-foreground">
                      {selected.links.length} link{selected.links.length === 1 ? "" : "s"} in this
                      message
                    </summary>
                    <ul className="mt-2 space-y-1">
                      {selected.links.map((link, index) => (
                        <li key={`${link.href}-${index}`} className="break-all text-muted-foreground">
                          {link.href}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                {selected.attachments.length > 0 && (
                  <ul className="mt-7 space-y-2 border-t border-border pt-5">
                    {selected.attachments.map((attachment) => (
                      <li key={attachment.index}>
                        <a
                          href={attachmentUrl(selected, attachment, account)}
                          className="flex min-h-11 items-center gap-3 rounded-lg px-2 text-sm transition-colors duration-150 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                          <span className="truncate">{attachment.filename}</span>
                          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                            {readableSize(attachment.size)}
                          </span>
                        </a>
                      </li>
                    ))}
                  </ul>
                )}

                {selected.thread.length > 0 && (
                  <div className="mt-8 border-t border-border pt-5">
                    <h3 className="text-sm font-medium">Rest of this thread</h3>
                    <ul className="mt-2">
                      {selected.thread.map((neighbour) => (
                        <li key={neighbour.uid}>
                          <button
                            type="button"
                            onClick={() =>
                              void openMessage({
                                uid: neighbour.uid,
                                folder: selected.folder,
                                unread: false,
                              })
                            }
                            className="flex min-h-11 w-full items-baseline gap-3 rounded-lg px-2 text-left text-sm transition-colors duration-150 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <span className="min-w-0 flex-1 truncate">{neighbour.sender}</span>
                            <time className="shrink-0 text-xs text-muted-foreground">
                              {friendlyDate(neighbour.date)}
                            </time>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </article>
          ) : (
            <div className="m-auto px-8 text-center text-muted-foreground">
              <Mail className="mx-auto mb-3 size-7" aria-hidden="true" />
              <p className="text-sm">Choose a message to read it.</p>
            </div>
          )}
        </main>
      </div>

      <Button
        className="fixed bottom-6 right-6 h-14 gap-2 md:hidden"
        onClick={() => setComposing({})}
        aria-label="Compose a message"
      >
        <PenLine className="size-4" />
      </Button>

      {composing && (
        <Compose
          account={account}
          initial={composing}
          onClose={() => setComposing(null)}
          onSent={() => {
            setComposing(null);
            setAssistant("Message sent.");
            void loadList();
          }}
        />
      )}
    </section>
  );
}

function replyDraft(message: MailMessage, body: string): Partial<Draft> {
  const subject = message.subject.toLowerCase().startsWith("re:")
    ? message.subject
    : `Re: ${message.subject}`;
  return {
    to: message.sender,
    subject,
    body,
    in_reply_to: message.message_id,
    references: message.message_id,
  };
}

/** Writing tone, signature, and automatic triage. No mail content is stored. */
function Preferences({
  value,
  onSave,
  onError,
}: {
  value: AiPreferences;
  onSave: (preferences: AiPreferences) => void;
  onError: (reason: unknown) => void;
}) {
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      onSave(
        await api<AiPreferences>("/preferences", {
          method: "PUT",
          body: JSON.stringify(draft),
        }),
      );
    } catch (reason) {
      onError(reason);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border-b border-border px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="mailroom-tone">Tone</Label>
          <select
            id="mailroom-tone"
            value={draft.tone}
            onChange={(event) => setDraft({ ...draft, tone: event.target.value })}
            className="h-11 rounded-lg border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {["neutral", "warm", "brief", "formal"].map((tone) => (
              <option key={tone} value={tone}>
                {tone}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-56 flex-1 space-y-2">
          <Label htmlFor="mailroom-signature">Signature</Label>
          <Input
            id="mailroom-signature"
            value={draft.signature}
            onChange={(event) => setDraft({ ...draft, signature: event.target.value })}
            placeholder="Added to assisted drafts"
            className="h-11"
          />
        </div>
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={draft.auto_triage}
            onChange={(event) => setDraft({ ...draft, auto_triage: event.target.checked })}
            className="size-4"
          />
          Suggest triage automatically
        </label>
        <Button className="h-11" disabled={saving} onClick={() => void save()}>
          Save
        </Button>
      </div>
    </div>
  );
}

function MailroomLoading() {
  return (
    <div className="min-h-[calc(100dvh-9rem)] rounded-2xl border border-border p-5">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="mt-8 h-24 w-full" />
      <Skeleton className="mt-3 h-24 w-full" />
    </div>
  );
}

function MessageListLoading() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}
