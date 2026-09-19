"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type FieldDefinition = {
  id: string;
  label: string;
  type: string;
  required: boolean;
  options: string[];
  multiline: boolean;
};

type ReviewComment = {
  id: string;
  author_kind: string;
  body: string;
  created_at: string;
};
type ReviewThread = {
  id: string;
  field_id?: string | null;
  block_id?: string | null;
  quote?: string | null;
  status: "open" | "addressed" | "resolved";
  comments: ReviewComment[];
};
type DocumentBlock = {
  id: string;
  type: "heading" | "legal" | "text" | "fields";
  text: string;
  field_ids?: string[];
};
type DocumentSection = { id: string; title: string; blocks: DocumentBlock[] };
type EditorData = {
  title: string;
  document: {
    id: string;
    status: string;
    current_revision: number;
    signature_url?: string | null;
  };
  fields: FieldDefinition[];
  sections: DocumentSection[];
  values: Record<string, unknown>;
  threads: ReviewThread[];
  editable: boolean;
  can_submit: boolean;
};

type Props = {
  token: string;
  documentId: string;
  onBack: () => void;
  onChanged: () => void;
};

const fieldBase =
  "w-full border-2 border-black bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[#fc920d] focus:ring-4 focus:ring-[#fc920d]/25 disabled:cursor-not-allowed disabled:bg-zinc-100";

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

export default function OnboardingDocumentEditor({
  token,
  documentId,
  onBack,
  onChanged,
}: Props) {
  const [editor, setEditor] = useState<EditorData | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState<Record<string, unknown>>({});
  const [saveState, setSaveState] = useState<
    "idle" | "dirty" | "saving" | "saved" | "conflict" | "error"
  >("idle");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [replying, setReplying] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const errorSummaryRef = useRef<HTMLDivElement>(null);
  const savingRef = useRef(false);
  const pendingSaveRef = useRef(false);
  const valuesRef = useRef(values);
  const dirtyRef = useRef(dirty);
  const revisionRef = useRef(0);
  const saveRef = useRef<() => Promise<boolean>>(async () => false);

  useEffect(() => {
    valuesRef.current = values;
  }, [values]);
  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  const load = useCallback(async () => {
    setError(null);
    const response = await fetch(
      `/api/onboarding/public/${token}/documents/${documentId}/editor`,
      { cache: "no-store" },
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : "The document could not be loaded.",
      );
    const next = body as EditorData;
    setEditor(next);
    setValues(next.values ?? {});
    setDirty({});
    revisionRef.current = next.document.current_revision;
    setSaveState("idle");
  }, [documentId, token]);

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message));
  }, [load]);

  const save = useCallback(async (): Promise<boolean> => {
    if (savingRef.current) {
      pendingSaveRef.current = true;
      return false;
    }
    const changes = dirtyRef.current;
    if (Object.keys(changes).length === 0) return true;
    savingRef.current = true;
    setSaveState("saving");
    setError(null);
    try {
      const response = await fetch(
        `/api/onboarding/public/${token}/documents/${documentId}/draft`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            base_revision: revisionRef.current,
            values: changes,
          }),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (response.status === 409) {
        setSaveState("conflict");
        setError(
          "This document changed in another tab. Reload it before continuing.",
        );
        return false;
      }
      if (!response.ok) {
        const detail = body.detail;
        if (detail && typeof detail === "object" && detail.fields)
          setFieldErrors(detail.fields);
        throw new Error(
          typeof detail === "string"
            ? detail
            : (detail?.message ?? "Your changes could not be saved."),
        );
      }
      const next = body as EditorData;
      setEditor(next);
      revisionRef.current = next.document.current_revision;
      setDirty((current) => {
        const remaining = { ...current };
        for (const [key, savedValue] of Object.entries(changes)) {
          if (remaining[key] === savedValue) delete remaining[key];
        }
        dirtyRef.current = remaining;
        return remaining;
      });
      setFieldErrors({});
      setSaveState("saved");
      return true;
    } catch (reason) {
      setSaveState("error");
      setError(
        reason instanceof Error
          ? reason.message
          : "Your changes could not be saved.",
      );
      return false;
    } finally {
      savingRef.current = false;
      if (pendingSaveRef.current) {
        pendingSaveRef.current = false;
        window.setTimeout(() => {
          void saveRef.current();
        }, 0);
      }
    }
  }, [documentId, token]);

  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  useEffect(() => {
    if (Object.keys(dirty).length === 0 || !editor?.editable) return;
    setSaveState("dirty");
    const timer = window.setTimeout(() => {
      void save();
    }, 900);
    return () => window.clearTimeout(timer);
  }, [dirty, editor?.editable, save]);

  useEffect(() => {
    if (error || Object.keys(fieldErrors).length > 0)
      errorSummaryRef.current?.focus();
  }, [error, fieldErrors]);

  const fieldsById = useMemo(
    () => new Map((editor?.fields ?? []).map((field) => [field.id, field])),
    [editor?.fields],
  );
  const completed = useMemo(
    () =>
      (editor?.fields ?? []).filter(
        (field) =>
          field.type === "signature" ||
          (values[field.id] !== undefined &&
            values[field.id] !== "" &&
            values[field.id] !== false),
      ).length,
    [editor?.fields, values],
  );
  const progress = editor?.fields.length
    ? Math.round((completed / editor.fields.length) * 100)
    : 0;

  const setField = (fieldId: string, value: unknown) => {
    setValues((current) => ({ ...current, [fieldId]: value }));
    setDirty((current) => {
      const next = { ...current, [fieldId]: value };
      dirtyRef.current = next;
      return next;
    });
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[fieldId];
      return next;
    });
  };

  const submit = async () => {
    const saved = await save();
    if (!saved) return;
    setError(null);
    const response = await fetch(
      `/api/onboarding/public/${token}/documents/${documentId}/submit`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_revision: revisionRef.current,
          confirmed_identity: confirmed,
        }),
      },
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body.detail;
      if (detail && typeof detail === "object" && detail.fields)
        setFieldErrors(detail.fields);
      setError(
        typeof detail === "string"
          ? detail
          : (detail?.message ?? "The document could not be submitted."),
      );
      return;
    }
    setEditor(body as EditorData);
    setConfirmed(false);
    onChanged();
  };

  const postReply = async (threadId: string) => {
    if (!reply.trim()) return;
    const response = await fetch(
      `/api/onboarding/public/${token}/review-threads/${threadId}/comments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: reply.trim() }),
      },
    );
    if (!response.ok) {
      setError("Your reply could not be posted.");
      return;
    }
    setReply("");
    setReplying(null);
    await load();
  };

  if (error && !editor)
    return (
      <div
        role="alert"
        className="border-2 border-red-800 bg-red-50 p-5 text-sm text-red-950"
      >
        {error}
      </div>
    );
  if (!editor)
    return (
      <div role="status" className="p-8 font-mono text-sm">
        Loading document editor…
      </div>
    );

  const renderField = (field: FieldDefinition) => {
    const value = values[field.id];
    const errorText = fieldErrors[field.id];
    const describedBy = errorText ? `${field.id}-error` : undefined;
    if (field.type === "signature") {
      return (
        <div className="flex items-center justify-between gap-3 border-2 border-dashed border-[#97192c] bg-[#fff8ef] p-3">
          <span className="font-semibold">Electronic signature</span>
          <span className="rounded-full border-2 border-[#97192c] px-3 py-1 font-mono text-[11px] font-bold uppercase text-[#97192c]">
            After approval
          </span>
        </div>
      );
    }
    if (field.type === "checkbox") {
      return (
        <label className="flex items-start gap-3 border-2 border-zinc-300 p-3 text-sm">
          <input
            id={`${field.id}-control`}
            className="mt-0.5 size-5 accent-[#97192c]"
            type="checkbox"
            checked={value === true}
            disabled={!editor.editable}
            onChange={(event) => setField(field.id, event.target.checked)}
            aria-invalid={Boolean(errorText)}
            aria-describedby={describedBy}
          />
          <span>I confirm this statement.</span>
        </label>
      );
    }
    if (field.type === "choice") {
      return (
        <select
          id={`${field.id}-control`}
          className={fieldBase}
          value={String(value ?? "")}
          disabled={!editor.editable}
          required={field.required}
          onChange={(event) => setField(field.id, event.target.value)}
          aria-invalid={Boolean(errorText)}
          aria-describedby={describedBy}
        >
          <option value="">Select an option</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    }
    if (field.multiline) {
      return (
        <textarea
          id={`${field.id}-control`}
          className={`${fieldBase} min-h-28 resize-y`}
          value={String(value ?? "")}
          disabled={!editor.editable}
          required={field.required}
          onChange={(event) => setField(field.id, event.target.value)}
          aria-invalid={Boolean(errorText)}
          aria-describedby={describedBy}
        />
      );
    }
    const inputType = ["date", "email", "number", "tel", "url"].includes(
      field.type,
    )
      ? field.type
      : "text";
    return (
      <input
        id={`${field.id}-control`}
        className={fieldBase}
        type={inputType}
        value={String(value ?? "")}
        disabled={!editor.editable}
        required={field.required}
        onChange={(event) => setField(field.id, event.target.value)}
        aria-invalid={Boolean(errorText)}
        aria-describedby={describedBy}
      />
    );
  };

  return (
    <div className="space-y-5">
      <div className="sticky top-0 z-20 border-2 border-black bg-[#f7f4ef] p-3 shadow-[0_4px_0_#120f0a]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={onBack}
            className="font-mono text-xs font-black uppercase underline focus:outline-none focus:ring-4 focus:ring-[#fc920d]/40"
          >
            ← All documents
          </button>
          <span className="border-2 border-black bg-white px-3 py-1 font-mono text-[11px] font-bold uppercase">
            {statusLabel(editor.document.status)}
          </span>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <div
            className="h-3 flex-1 overflow-hidden border-2 border-black bg-white"
            role="progressbar"
            aria-label="Document completion"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
          >
            <div
              className="h-full bg-[#fc920d]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="font-mono text-xs font-bold">{progress}%</span>
        </div>
        <p className="mt-2 font-mono text-xs" aria-live="polite">
          {saveState === "dirty"
            ? "Unsaved changes"
            : saveState === "saving"
              ? "Saving…"
              : saveState === "saved"
                ? `Saved revision ${editor.document.current_revision}`
                : saveState === "conflict"
                  ? "Editing conflict"
                  : ""}
        </p>
      </div>

      {error || Object.keys(fieldErrors).length > 0 ? (
        <div
          ref={errorSummaryRef}
          tabIndex={-1}
          role="alert"
          className="border-2 border-red-800 bg-red-50 p-4 text-sm text-red-950 outline-none focus:ring-4 focus:ring-red-300"
        >
          <p className="font-black">Please fix the following</p>
          {error ? <p className="mt-1">{error}</p> : null}
          <ul className="mt-2 list-disc pl-5">
            {Object.entries(fieldErrors).map(([id, message]) => (
              <li key={id}>
                <a className="underline" href={`#${id}`}>
                  {fieldsById.get(id)?.label ?? id}: {message}
                </a>
              </li>
            ))}
          </ul>
          {saveState === "conflict" ? (
            <button
              type="button"
              onClick={() => void load()}
              className="mt-3 border-2 border-black bg-white px-3 py-2 font-mono text-xs font-black uppercase"
            >
              Reload latest revision
            </button>
          ) : null}
        </div>
      ) : null}

      <header className="border-2 border-black bg-[#3c0a12] p-6 text-white shadow-[5px_5px_0_#120f0a]">
        <p className="font-mono text-xs uppercase tracking-widest text-[#fc920d]">
          OOXML document · revision {editor.document.current_revision}
        </p>
        <h1 className="mt-2 text-3xl font-black uppercase">{editor.title}</h1>
        <p className="mt-2 max-w-2xl text-sm text-white/75">
          Fill the highlighted fields in the document. Your place is saved
          automatically and every submitted revision remains in the audit
          history.
        </p>
      </header>

      <nav
        aria-label="Document sections"
        className="flex gap-2 overflow-x-auto pb-2"
      >
        {editor.sections.map((section, index) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="shrink-0 border-2 border-black bg-white px-3 py-2 font-mono text-xs font-bold uppercase focus:ring-4 focus:ring-[#fc920d]/30"
          >
            {index + 1}. {section.title}
          </a>
        ))}
      </nav>

      {editor.sections.map((section) => (
        <section
          id={section.id}
          key={section.id}
          aria-labelledby={`${section.id}-title`}
          className="scroll-mt-28 border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a] sm:p-7"
        >
          <h2
            id={`${section.id}-title`}
            className="mb-5 border-b-2 border-black pb-3 text-xl font-black uppercase"
          >
            {section.title}
          </h2>
          <div className="space-y-5">
            {section.blocks.map((block) => {
              const blockThreads = editor.threads.filter(
                (thread) =>
                  thread.block_id === block.id ||
                  block.field_ids?.includes(thread.field_id ?? ""),
              );
              return (
                <div
                  key={block.id}
                  className={
                    blockThreads.some((thread) => thread.status !== "resolved")
                      ? "border-l-4 border-[#fc920d] pl-4"
                      : ""
                  }
                >
                  {block.type === "legal" ? (
                    <p className="text-sm leading-7 text-zinc-700">
                      {block.text}
                    </p>
                  ) : block.type === "heading" ? (
                    <h3 className="font-black uppercase">{block.text}</h3>
                  ) : (
                    <p className="text-sm font-semibold">{block.text}</p>
                  )}
                  {block.field_ids?.map((fieldId) => {
                    const field = fieldsById.get(fieldId);
                    if (!field) return null;
                    return (
                      <div
                        id={field.id}
                        key={field.id}
                        className="mt-3 scroll-mt-32"
                      >
                        <label
                          className="mb-1 block text-sm font-black"
                          htmlFor={`${field.id}-control`}
                        >
                          {field.label}
                          {field.required ? (
                            <span aria-hidden="true" className="text-red-700">
                              {" "}
                              *
                            </span>
                          ) : null}
                          <span className="sr-only">
                            {field.required ? " required" : ""}
                          </span>
                        </label>
                        <div>
                          {renderField(field)}
                        </div>
                        {fieldErrors[field.id] ? (
                          <p
                            id={`${field.id}-error`}
                            className="mt-1 text-sm font-semibold text-red-800"
                          >
                            {fieldErrors[field.id]}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                  {blockThreads.map((thread) => (
                    <aside
                      key={thread.id}
                      aria-label={`Review thread: ${thread.status}`}
                      className="mt-4 border-2 border-[#97192c] bg-[#fff8ef] p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-mono text-[11px] font-black uppercase text-[#97192c]">
                          Review · {thread.status}
                        </p>
                        {thread.quote ? (
                          <span className="truncate text-xs text-zinc-500">
                            “{thread.quote}”
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 space-y-2">
                        {thread.comments.map((comment) => (
                          <div key={comment.id} className="text-sm">
                            <span className="font-bold">
                              {comment.author_kind === "hq"
                                ? "HQ reviewer"
                                : "You"}
                              :
                            </span>{" "}
                            {comment.body}
                          </div>
                        ))}
                      </div>
                      {thread.status !== "resolved" ? (
                        replying === thread.id ? (
                          <div className="mt-3 flex gap-2">
                            <label
                              className="sr-only"
                              htmlFor={`reply-${thread.id}`}
                            >
                              Reply to review
                            </label>
                            <input
                              id={`reply-${thread.id}`}
                              className={fieldBase}
                              value={reply}
                              onChange={(event) => setReply(event.target.value)}
                            />
                            <button
                              type="button"
                              onClick={() => void postReply(thread.id)}
                              className="border-2 border-black bg-[#fc920d] px-3 font-mono text-xs font-black uppercase"
                            >
                              Post
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setReplying(thread.id)}
                            className="mt-3 font-mono text-xs font-black uppercase underline"
                          >
                            Reply
                          </button>
                        )
                      ) : null}
                    </aside>
                  ))}
                </div>
              );
            })}
          </div>
        </section>
      ))}

      {editor.editable ? (
        <section className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a]">
          <h2 className="text-lg font-black uppercase">Request HQ review</h2>
          <p className="mt-1 text-sm text-zinc-600">
            Submitting freezes this revision. If HQ requests changes, this
            editor reopens with comments attached to the relevant fields.
          </p>
          <label className="mt-4 flex items-start gap-3 border-t-2 border-dashed border-zinc-300 pt-4 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-5 accent-[#97192c]"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>
              I confirm that these details belong to me and are ready for HQ
              review.
            </span>
          </label>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void save()}
              className="border-2 border-black bg-white px-4 py-3 font-mono text-xs font-black uppercase"
            >
              Save now
            </button>
            <button
              type="button"
              disabled={!confirmed || saveState === "saving"}
              onClick={() => void submit()}
              className="border-2 border-black bg-[#fc920d] px-5 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Submit revision for review
            </button>
          </div>
        </section>
      ) : (
        <div
          role="status"
          className="border-2 border-emerald-800 bg-emerald-50 p-4 text-sm text-emerald-950"
        >
          This revision is locked while HQ reviews it. You can still read and
          reply to review threads.
        </div>
      )}
    </div>
  );
}
