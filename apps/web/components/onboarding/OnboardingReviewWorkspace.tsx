"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type Field = {
  id: string;
  label: string;
  type: string;
  required: boolean;
  editable_by?: string;
  options: string[];
  multiline: boolean;
};
type Comment = {
  id: string;
  author_kind: string;
  body: string;
  created_at: string;
};
type Thread = {
  id: string;
  field_id?: string | null;
  block_id?: string | null;
  quote?: string | null;
  status: string;
  comments: Comment[];
};
type Block = { id: string; type: string; text: string; field_ids?: string[] };
type Section = { id: string; title: string; blocks: Block[] };
type Editor = {
  title: string;
  document: {
    id: string;
    document_key: string;
    status: string;
    current_revision: number;
    signature_url?: string | null;
  };
  fields: Field[];
  sections: Section[];
  values: Record<string, unknown>;
  threads: Thread[];
  editable: boolean;
  can_compile: boolean;
  can_approve: boolean;
  review_block_reason?: string | null;
};

const inputClass =
  "w-full border-2 border-black bg-white px-3 py-2 text-sm outline-none focus:border-[#fc920d] focus:ring-4 focus:ring-[#fc920d]/25 disabled:bg-zinc-100";

export default function OnboardingReviewWorkspace({
  caseId,
  documentId,
}: {
  caseId: string;
  documentId: string;
}) {
  const [editor, setEditor] = useState<Editor | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [commenting, setCommenting] = useState<{
    fieldId?: string;
    blockId?: string;
    quote?: string;
  } | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await fetch(
      `/api/onboarding/cases/${caseId}/documents/${documentId}/editor`,
      { cache: "no-store" },
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : "Could not load this review.",
      );
    setEditor(body as Editor);
    setValues((body as Editor).values ?? {});
  }, [caseId, documentId]);

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message));
  }, [load]);
  const fields = useMemo(
    () => new Map((editor?.fields ?? []).map((field) => [field.id, field])),
    [editor],
  );
  const openThreads =
    editor?.threads.filter((thread) => thread.status !== "resolved").length ??
    0;

  const mutate = async (
    path: string,
    method: string,
    body?: unknown,
    success?: string,
  ) => {
    setBusy(path);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/onboarding/cases/${caseId}${path}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : (payload.detail?.message ?? "The action could not be completed."),
        );
      setNotice(success ?? "Saved.");
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The action could not be completed.",
      );
    } finally {
      setBusy(null);
    }
  };

  const saveHqFields = () => {
    if (!editor) return;
    const hqValues = Object.fromEntries(
      editor.fields
        .filter(
          (field) => field.editable_by === "hq" && field.type !== "signature",
        )
        .map((field) => [field.id, values[field.id]]),
    );
    void mutate(
      `/documents/${documentId}/draft`,
      "PATCH",
      { base_revision: editor.document.current_revision, values: hqValues },
      "HQ fields saved as a new revision.",
    );
  };

  const createThread = () => {
    if (!commenting || !comment.trim()) return;
    void mutate(
      `/documents/${documentId}/review-threads`,
      "POST",
      {
        field_id: commenting.fieldId,
        block_id: commenting.blockId,
        quote: commenting.quote,
        body: comment.trim(),
      },
      "Review comment anchored.",
    ).then(() => {
      setComment("");
      setCommenting(null);
    });
  };

  const deleteWorkflow = async () => {
    if (
      !window.confirm(
        "Permanently delete this entire onboarding workflow?\n\nThis will void any active signature requests, notify all signers by email, and completely delete the case.",
      )
    ) {
      return;
    }
    setBusy("delete");
    try {
      const response = await fetch(`/api/onboarding/cases/${caseId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Could not delete this workflow.",
        );
      }
      window.location.href = "/dashboard/onboarding";
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not delete this workflow.",
      );
      setBusy(null);
    }
  };


  if (!editor)
    return (
      <main className="mx-auto max-w-6xl p-8" role={error ? "alert" : "status"}>
        {error ?? "Loading review workspace…"}
      </main>
    );

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6 lg:p-8">
      <a
        href="#review-document"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:border-2 focus:border-black focus:bg-[#fc920d] focus:p-3"
      >
        Skip to document
      </a>
      <header className="border-2 border-black bg-[#3c0a12] p-5 text-white shadow-[5px_5px_0_#120f0a]">
        <Link
          href="/dashboard/onboarding"
          className="font-mono text-xs font-black uppercase text-[#fc920d] underline"
        >
          ← All cases
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-[#fc920d]">
              HQ review · revision {editor.document.current_revision}
            </p>
            <h1 className="mt-1 text-3xl font-black uppercase">
              {editor.title}
            </h1>
          </div>
          <div className="flex gap-2">
            <span className="border-2 border-white px-3 py-1 font-mono text-xs uppercase">
              {editor.document.status.replaceAll("_", " ")}
            </span>
            <span className="border-2 border-[#fc920d] px-3 py-1 font-mono text-xs uppercase">
              {openThreads} unresolved
            </span>
          </div>
        </div>
      </header>
      <div aria-live="polite">
        {error ? (
          <div
            role="alert"
            className="border-2 border-red-800 bg-red-50 p-4 text-red-950"
          >
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="border-2 border-emerald-800 bg-emerald-50 p-4 text-emerald-950">
            {notice}
          </div>
        ) : null}
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <article id="review-document" className="space-y-5">
          {editor.sections.map((section) => (
            <section
              key={section.id}
              aria-labelledby={`${section.id}-heading`}
              className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a]"
            >
              <h2
                id={`${section.id}-heading`}
                className="border-b-2 border-black pb-3 text-xl font-black uppercase"
              >
                {section.title}
              </h2>
              <div className="mt-4 space-y-5">
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
                        blockThreads.some(
                          (thread) => thread.status !== "resolved",
                        )
                          ? "border-l-4 border-[#fc920d] pl-4"
                          : ""
                      }
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p
                          className={
                            block.type === "legal"
                              ? "text-sm leading-7 text-zinc-700"
                              : "font-semibold"
                          }
                        >
                          {block.text}
                        </p>
                        <button
                          type="button"
                          onClick={() =>
                            setCommenting({
                              blockId: block.id,
                              quote: block.text.slice(0, 180),
                            })
                          }
                          className="shrink-0 font-mono text-[11px] font-black uppercase text-[#97192c] underline"
                        >
                          Comment
                        </button>
                      </div>
                      {block.field_ids?.map((fieldId) => {
                        const field = fields.get(fieldId);
                        if (!field) return null;
                        const editable =
                          field.editable_by === "hq" &&
                          field.type !== "signature";
                        return (
                          <div
                            key={field.id}
                            className="mt-3 border-2 border-zinc-300 p-3"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <label
                                htmlFor={`review-${field.id}`}
                                className="text-sm font-black"
                              >
                                {field.label}
                                {field.required ? " *" : ""}
                              </label>
                              <button
                                type="button"
                                onClick={() =>
                                  setCommenting({
                                    fieldId: field.id,
                                    blockId: block.id,
                                    quote: String(values[field.id] ?? "").slice(
                                      0,
                                      180,
                                    ),
                                  })
                                }
                                className="font-mono text-[11px] font-black uppercase text-[#97192c] underline"
                              >
                                Comment
                              </button>
                            </div>
                            {editable ? (
                              field.multiline ? (
                                <textarea
                                  id={`review-${field.id}`}
                                  className={`${inputClass} mt-2 min-h-24`}
                                  value={String(values[field.id] ?? "")}
                                  onChange={(event) =>
                                    setValues((current) => ({
                                      ...current,
                                      [field.id]: event.target.value,
                                    }))
                                  }
                                />
                              ) : (
                                <input
                                  id={`review-${field.id}`}
                                  className={`${inputClass} mt-2`}
                                  type={field.type === "date" ? "date" : "text"}
                                  value={String(values[field.id] ?? "")}
                                  onChange={(event) =>
                                    setValues((current) => ({
                                      ...current,
                                      [field.id]: event.target.value,
                                    }))
                                  }
                                />
                              )
                            ) : (
                              <div
                                id={`review-${field.id}`}
                                tabIndex={0}
                                className="mt-2 min-h-10 bg-zinc-50 px-3 py-2 text-sm"
                              >
                                {field.type === "signature" ? (
                                  <span className="font-mono text-xs uppercase text-[#97192c]">
                                    Signature chip added after approval
                                  </span>
                                ) : (
                                  String(values[field.id] ?? "Not provided")
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {blockThreads.map((thread) => (
                        <aside
                          key={thread.id}
                          className="mt-3 border-2 border-[#97192c] bg-[#fff8ef] p-3"
                          aria-label={`Review thread ${thread.status}`}
                        >
                          <div className="flex justify-between gap-3">
                            <span className="font-mono text-xs font-black uppercase">
                              {thread.status}
                            </span>
                            {thread.status !== "resolved" ? (
                              <button
                                type="button"
                                onClick={() =>
                                  void mutate(
                                    `/review-threads/${thread.id}`,
                                    "PATCH",
                                    { status: "resolved" },
                                    "Thread resolved.",
                                  )
                                }
                                className="font-mono text-xs font-black uppercase underline"
                              >
                                Resolve
                              </button>
                            ) : null}
                          </div>
                          {thread.comments.map((item) => (
                            <p key={item.id} className="mt-2 text-sm">
                              <strong>
                                {item.author_kind === "hq"
                                  ? "HQ"
                                  : "Participant"}
                                :
                              </strong>{" "}
                              {item.body}
                            </p>
                          ))}
                        </aside>
                      ))}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </article>
        <aside
          className="sticky top-4 space-y-4 border-2 border-black bg-[#f7f4ef] p-4 shadow-[4px_4px_0_#120f0a]"
          aria-label="Review actions"
        >
          <h2 className="font-black uppercase">Review controls</h2>
          <p className="text-sm text-zinc-700">
            Comments stay attached to their field or paragraph across revisions.
          </p>
          {commenting ? (
            <div className="border-2 border-[#97192c] bg-white p-3">
              <label htmlFor="review-comment" className="text-sm font-black">
                Review comment
              </label>
              <textarea
                id="review-comment"
                autoFocus
                className={`${inputClass} mt-2 min-h-28`}
                value={comment}
                onChange={(event) => setComment(event.target.value)}
              />
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={createThread}
                  disabled={!comment.trim() || Boolean(busy)}
                  className="border-2 border-black bg-[#fc920d] px-3 py-2 font-mono text-xs font-black uppercase disabled:opacity-50"
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => setCommenting(null)}
                  className="border-2 border-black px-3 py-2 font-mono text-xs font-black uppercase"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
          {editor.fields.some(
            (field) => field.editable_by === "hq" && field.type !== "signature",
          ) ? (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={saveHqFields}
              className="w-full border-2 border-black bg-white px-3 py-3 font-mono text-xs font-black uppercase"
            >
              Save HQ fields
            </button>
          ) : null}
          {editor.document.status === "review_requested" ? (
            <>
              {!editor.can_approve && editor.review_block_reason ? (
                <p className="border-2 border-amber-800 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
                  {editor.review_block_reason}
                </p>
              ) : null}
              <button
                type="button"
                disabled={Boolean(busy) || !editor.can_approve}
                onClick={() =>
                  void mutate(
                    `/documents/${documentId}/request-changes`,
                    "POST",
                    {},
                    "Changes requested; the participant can edit again.",
                  )
                }
                className="w-full border-2 border-black bg-white px-3 py-3 font-mono text-xs font-black uppercase disabled:cursor-not-allowed disabled:opacity-50"
              >
                Request changes
              </button>
              <button
                type="button"
                disabled={Boolean(busy) || openThreads > 0 || !editor.can_approve}
                onClick={() =>
                  void mutate(
                    `/documents/${documentId}/approve`,
                    "POST",
                    undefined,
                    "Revision approved. It is ready for explicit compilation.",
                  )
                }
                className="w-full border-2 border-black bg-emerald-300 px-3 py-3 font-mono text-xs font-black uppercase disabled:opacity-50"
              >
                Approve revision
              </button>
            </>
          ) : null}
          {editor.can_compile ? (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() =>
                void mutate(
                  `/documents/${documentId}/compile`,
                  "POST",
                  { base_revision: editor.document.current_revision },
                  "DOCX and PDF compiled; cryptographic signing has started.",
                )
              }
              className="w-full border-2 border-black bg-[#fc920d] px-3 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a]"
            >
              Compile & start signing
            </button>
          ) : null}
          {editor.document.signature_url ? (
            <a
              href={editor.document.signature_url}
              className="block w-full border-2 border-black bg-[#97192c] px-3 py-3 text-center font-mono text-xs font-black uppercase text-white shadow-[3px_3px_0_#120f0a]"
            >
              Open signing ceremony
            </a>
          ) : null}
          {editor.document.status === "signing" ? (
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() =>
                void mutate(
                  `/documents/${documentId}/remind`,
                  "POST",
                  undefined,
                  "Reminder sent to pending signers.",
                )
              }
              className="w-full border-2 border-black bg-[#fdb32b] px-3 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a] hover:bg-[#fc920d] disabled:opacity-50"
            >
              {busy === `/documents/${documentId}/remind`
                ? "Reminding…"
                : "Remind signers"}
            </button>
          ) : null}
          <div className="border-t border-zinc-300 pt-3">
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={deleteWorkflow}
              className="w-full border-2 border-rose-800 bg-rose-50 px-3 py-2.5 font-mono text-xs font-black uppercase text-rose-900 shadow-[2px_2px_0_#120f0a] hover:bg-rose-100 disabled:opacity-50"
            >
              {busy === "delete" ? "Deleting…" : "Delete workflow"}
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
