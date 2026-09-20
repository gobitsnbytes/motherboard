"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ageOnDate } from "../../../lib/onboarding-age";

type ParticipantRow = {
  id: string;
  role: string;
  name: string;
  email: string;
  status: string;
  portal_url?: string | null;
  documents: Array<{
    id: string;
    status: string;
    document_key: string;
    signature_request_id?: string | null;
  }>;
};
type CaseRow = {
  id: string;
  title: string;
  kind: string;
  status: string;
  created_by?: string | null;
  reviewer_id?: string | null;
  documents: Array<{ id: string; status: string; document_key: string }>;
  participants: ParticipantRow[];
};
type Reviewer = { id: string; display_name: string; email?: string | null };

function apiErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((issue) =>
        typeof issue === "object" && issue !== null && "msg" in issue
          ? String(issue.msg)
          : null,
      )
      .filter(Boolean)
      .join(" ") || fallback;
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String(detail.message);
  }
  return fallback;
}

export default function OnboardingDashboardPage() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [kind, setKind] = useState("volunteer");
  const [title, setTitle] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [dob, setDob] = useState("");
  const [guardianName, setGuardianName] = useState("");
  const [guardianEmail, setGuardianEmail] = useState("");
  const [forkName, setForkName] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [editingParticipantId, setEditingParticipantId] = useState<
    string | null
  >(null);
  const [emailDraft, setEmailDraft] = useState("");
  const [savingParticipantId, setSavingParticipantId] = useState<string | null>(
    null,
  );
  const [resendingParticipantId, setResendingParticipantId] = useState<
    string | null
  >(null);
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null);
  const [remindingCaseId, setRemindingCaseId] = useState<string | null>(null);

  const participantAge = ageOnDate(dob);
  const isMinor = participantAge !== null && participantAge < 18;
  const isTooYoung = participantAge !== null && participantAge < 13;


  const load = async () => {
    const [casesResponse, reviewersResponse] = await Promise.all([
      fetch("/api/onboarding/cases", { cache: "no-store" }),
      fetch("/api/onboarding/reviewers", { cache: "no-store" }),
    ]);
    if (casesResponse.ok) setCases(await casesResponse.json());
    if (reviewersResponse.ok) setReviewers(await reviewersResponse.json());
  };
  useEffect(() => {
    load().catch(() => setError("Could not load onboarding cases."));
  }, []);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    const response = await fetch("/api/onboarding/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind,
        title,
        fork_name: kind === "fork" ? forkName : undefined,
        reviewer_id: reviewerId || undefined,
        participant: {
          name,
          email,
          date_of_birth: dob,
          is_volunteer: true,
          parent: isMinor
            ? { name: guardianName, email: guardianEmail }
            : undefined,
        },
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(apiErrorMessage(body.detail, "Could not create case."));
      return;
    }
    setTitle("");
    setName("");
    setEmail("");
    setDob("");
    setGuardianName("");
    setGuardianEmail("");
    setForkName("");
    setReviewerId("");
    await load();
  };

  const assignReviewer = async (caseId: string, assignedReviewerId: string) => {
    setError(null);
    const response = await fetch(`/api/onboarding/cases/${caseId}/reviewer`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_id: assignedReviewerId }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(apiErrorMessage(body.detail, "Could not assign the reviewer."));
      return;
    }
    await load();
  };

  const updateEmail = async (caseId: string, participantId: string) => {
    setError(null);
    setMessage(null);
    setSavingParticipantId(participantId);
    try {
      const response = await fetch(
        `/api/onboarding/cases/${caseId}/participants/${participantId}/email`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: emailDraft }),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Could not update the email.",
        );
      setEditingParticipantId(null);
      setEmailDraft("");
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not update the email.",
      );
    } finally {
      setSavingParticipantId(null);
    }
  };

  const resendInvite = async (caseId: string, participantId: string) => {
    setError(null);
    setMessage(null);
    setResendingParticipantId(participantId);
    try {
      const response = await fetch(
        `/api/onboarding/cases/${caseId}/participants/${participantId}/resend`,
        { method: "POST" },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Could not resend the invite.",
        );
      setMessage(
        body.email_sent
          ? `A fresh onboarding invite was sent to ${body.email}. Older links are now invalid.`
          : `The portal link was refreshed for ${body.email}, but SMTP is not configured to send it.`,
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not resend the invite.",
      );
    } finally {
      setResendingParticipantId(null);
    }
  };

  const deleteCase = async (caseId: string, caseTitle: string) => {
    if (
      !window.confirm(
        `Permanently delete onboarding workflow "${caseTitle}"?\n\nThis will cancel any active signature requests, notify all signers by email, and completely remove the case.`,
      )
    ) {
      return;
    }
    setError(null);
    setMessage(null);
    setDeletingCaseId(caseId);
    try {
      const response = await fetch(`/api/onboarding/cases/${caseId}`, {
        method: "DELETE",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Could not delete the onboarding workflow.",
        );
      }
      const notified =
        Array.isArray(body.notified) && body.notified.length > 0
          ? ` Signers notified: ${body.notified.join(", ")}.`
          : "";
      setMessage(`Deleted onboarding workflow "${caseTitle}".${notified}`);
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not delete the onboarding workflow.",
      );
    } finally {
      setDeletingCaseId(null);
    }
  };

  const remindSigners = async (caseId: string, caseTitle: string) => {
    setError(null);
    setMessage(null);
    setRemindingCaseId(caseId);
    try {
      const response = await fetch(`/api/onboarding/cases/${caseId}/remind`, {
        method: "POST",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Could not send reminders.",
        );
      }
      if (body.reminded_count === 0) {
        setMessage(`No pending signers or participants to remind for "${caseTitle}".`);
      } else {
        const emailStatus = body.email_sent
          ? "Reminder email(s) sent"
          : "Portal link(s) refreshed (SMTP disabled)";
        setMessage(
          `${emailStatus} for ${body.reminded_count} recipient(s): ${body.reminded.join(", ")}.`,
        );
      }
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not send reminders.",
      );
    } finally {
      setRemindingCaseId(null);
    }
  };


  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-3 border-2 border-black bg-[#3c0a12] p-6 text-white shadow-[6px_6px_0_#120f0a] sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-[#fc920d]">
            workflow / onboarding
          </p>
          <h1 className="mt-2 text-3xl font-black uppercase">
            Digital onboarding
          </h1>
          <p className="mt-1 text-sm text-white/75">
            Portal collection, evidence, review, and sealed PDF hand-off.
          </p>
        </div>
        <span className="font-mono text-xs uppercase text-[#fc920d]">
          IAM reviewed
        </span>
      </header>
      {error && (
        <div className="border-2 border-red-700 bg-red-50 p-4 font-mono text-sm text-red-900">
          {error}
        </div>
      )}
      {message && (
        <div className="border-2 border-emerald-800 bg-emerald-50 p-4 font-mono text-sm text-emerald-900">
          {message}
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <form
          onSubmit={create}
          className="space-y-4 border-2 border-black bg-white p-5 shadow-[4px_4px_0_#120f0a]"
        >
          <h2 className="text-lg font-black uppercase">Start a case</h2>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm"
          >
            <option value="volunteer">Volunteer</option>
            <option value="fork">Fork lead</option>
          </select>
          <input
            required
            placeholder="Case title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm"
          />
          <input
            required
            placeholder="Person name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm"
          />
          <input
            required
            type="email"
            placeholder="Person email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm"
          />
          <input
            required
            type="date"
            value={dob}
            onChange={(e) => setDob(e.target.value)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm"
          />
          {isMinor && (
            <fieldset className="space-y-3 border-2 border-black bg-[#fff4dd] p-4">
              <legend className="px-2 font-mono text-xs font-black uppercase">
                Parent or legal guardian
              </legend>
              <p className="font-mono text-xs leading-relaxed text-zinc-700">
                This participant is under 18. Their guardian receives a separate
                portal link to complete the required consent form.
              </p>
              <label className="block space-y-1 font-mono text-xs font-bold">
                <span>Guardian full name</span>
                <input
                  required
                  autoComplete="name"
                  placeholder="Parent or guardian name"
                  value={guardianName}
                  onChange={(e) => setGuardianName(e.target.value)}
                  className="w-full border-2 border-black bg-white px-3 py-2 font-mono text-sm font-normal"
                />
              </label>
              <label className="block space-y-1 font-mono text-xs font-bold">
                <span>Guardian email</span>
                <input
                  required
                  type="email"
                  autoComplete="email"
                  placeholder="guardian@example.com"
                  value={guardianEmail}
                  onChange={(e) => setGuardianEmail(e.target.value)}
                  className="w-full border-2 border-black bg-white px-3 py-2 font-mono text-sm font-normal"
                />
              </label>
            </fieldset>
          )}
          {isTooYoung && (
            <p
              role="alert"
              className="border-2 border-red-700 bg-red-50 p-3 font-mono text-xs font-bold text-red-800"
            >
              Participants must be at least 13 years old for this onboarding
              workflow.
            </p>
          )}
          {kind === "fork" && (
            <input
              required
              placeholder="Fork name"
              value={forkName}
              onChange={(e) => setForkName(e.target.value)}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm"
            />
          )}
          <label className="block space-y-1 font-mono text-xs font-bold">
            <span>Independent reviewer</span>
            <select
              required
              value={reviewerId}
              onChange={(event) => setReviewerId(event.target.value)}
              className="w-full border-2 border-black bg-white px-3 py-2 font-mono text-sm font-normal"
            >
              <option value="">Select a reviewer</option>
              {reviewers.map((reviewer) => (
                <option key={reviewer.id} value={reviewer.id}>
                  {reviewer.display_name}{reviewer.email ? ` — ${reviewer.email}` : ""}
                </option>
              ))}
            </select>
            {reviewers.length === 0 ? (
              <span className="block text-amber-800">
                No other active user currently has onboarding.review permission.
              </span>
            ) : null}
          </label>
          <button
            disabled={isTooYoung}
            className="w-full border-2 border-black bg-[#fc920d] px-4 py-3 font-mono text-xs font-black uppercase shadow-[3px_3px_0_#120f0a] disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-600 disabled:shadow-none"
          >
            Create and send portal link
          </button>
        </form>
        <section className="space-y-3">
          <h2 className="text-lg font-black uppercase">Cases</h2>
          {cases.length === 0 ? (
            <div className="border-2 border-dashed border-zinc-400 p-8 font-mono text-sm text-zinc-600">
              No onboarding cases yet.
            </div>
          ) : (
            cases.map((item) => (
              <article
                key={item.id}
                className="border-2 border-black bg-white p-5 shadow-[3px_3px_0_#120f0a]"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="font-black uppercase">{item.title}</h3>
                    <p className="font-mono text-xs text-zinc-600">
                      {item.kind} / {item.status}
                    </p>
                    <p className="mt-1 font-mono text-[10px] uppercase text-zinc-500">
                      {item.reviewer_id
                        ? `Reviewer: ${reviewers.find((reviewer) => reviewer.id === item.reviewer_id)?.display_name ?? "assigned"}`
                        : "Reviewer not assigned"}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="border-2 border-black bg-[#f7f4ef] px-2 py-1 font-mono text-[10px] uppercase">
                      {item.participants.length} participant(s)
                    </span>
                    <button
                      type="button"
                      disabled={remindingCaseId === item.id || deletingCaseId === item.id}
                      onClick={() => remindSigners(item.id, item.title)}
                      className="border-2 border-black bg-[#fdb32b] px-2.5 py-1 font-mono text-[10px] font-black uppercase shadow-[2px_2px_0_#120f0a] hover:bg-[#fc920d] disabled:opacity-50"
                      title="Send reminder emails to all pending participants and signers"
                    >
                      {remindingCaseId === item.id ? "Reminding…" : "Remind signers"}
                    </button>
                    <button
                      type="button"
                      disabled={deletingCaseId === item.id || remindingCaseId === item.id}
                      onClick={() => deleteCase(item.id, item.title)}
                      className="border-2 border-black bg-rose-600 px-2.5 py-1 font-mono text-[10px] font-black uppercase text-white shadow-[2px_2px_0_#120f0a] hover:bg-rose-700 disabled:opacity-50"
                      title="Permanently delete this onboarding workflow and notify all signers"
                    >
                      {deletingCaseId === item.id ? "Deleting…" : "Delete"}
                    </button>
                  </div>
                </div>
                {!item.reviewer_id && reviewers.length > 0 ? (
                  <label className="mt-4 block max-w-sm space-y-1 font-mono text-xs font-bold">
                    <span>Assign independent reviewer</span>
                    <select
                      defaultValue=""
                      onChange={(event) => {
                        if (event.target.value) void assignReviewer(item.id, event.target.value);
                      }}
                      className="w-full border-2 border-black bg-white px-3 py-2 font-mono text-xs font-normal"
                    >
                      <option value="">Select reviewer</option>
                      {reviewers.map((reviewer) => (
                        <option key={reviewer.id} value={reviewer.id}>{reviewer.display_name}</option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <div className="mt-3 space-y-2">
                  {item.participants.map((person) => {
                    const canResendInvite =
                      person.status === "invited" &&
                      person.documents.length > 0 &&
                      person.documents.every(
                        (document) =>
                          document.status === "awaiting_completion" &&
                          !document.signature_request_id,
                      );
                    const canEditEmail =
                      person.role === "participant" && canResendInvite;
                    const isEditing = editingParticipantId === person.id;
                    return (
                      <div
                        key={person.id}
                        className="border-t border-zinc-200 pt-2 text-sm"
                      >
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <span>
                            {person.name}{" "}
                            <span className="font-mono text-xs text-zinc-500">
                              {person.status}
                            </span>
                          </span>
                          <div className="flex items-center gap-3">
                            {canResendInvite && (
                              <button
                                type="button"
                                disabled={resendingParticipantId === person.id}
                                onClick={() => resendInvite(item.id, person.id)}
                                className="font-mono text-xs font-bold text-[#97192c] underline disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                {resendingParticipantId === person.id
                                  ? "Sending…"
                                  : "Resend invite"}
                              </button>
                            )}
                            {canEditEmail && (
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingParticipantId(
                                    isEditing ? null : person.id,
                                  );
                                  setEmailDraft(person.email);
                                }}
                                className="font-mono text-xs font-bold text-[#97192c] underline"
                              >
                                Edit email
                              </button>
                            )}
                            {person.portal_url && (
                              <a
                                href={person.portal_url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-mono text-xs font-bold text-[#97192c] underline"
                              >
                                Copy/open portal
                              </a>
                            )}
                          </div>
                        </div>
                        {isEditing && (
                          <form
                            onSubmit={(event) => {
                              event.preventDefault();
                              updateEmail(item.id, person.id);
                            }}
                            className="mt-3 flex flex-col gap-2 sm:flex-row"
                          >
                            <label
                              className="sr-only"
                              htmlFor={`email-${person.id}`}
                            >
                              Correct email for {person.name}
                            </label>
                            <input
                              id={`email-${person.id}`}
                              required
                              type="email"
                              value={emailDraft}
                              onChange={(event) =>
                                setEmailDraft(event.target.value)
                              }
                              className="min-w-0 flex-1 border-2 border-black px-3 py-2 font-mono text-sm"
                            />
                            <button
                              disabled={savingParticipantId === person.id}
                              className="border-2 border-black bg-[#fc920d] px-3 py-2 font-mono text-xs font-black uppercase disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {savingParticipantId === person.id
                                ? "Saving…"
                                : "Save email"}
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingParticipantId(null)}
                              className="border-2 border-black px-3 py-2 font-mono text-xs font-black uppercase"
                            >
                              Cancel
                            </button>
                          </form>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 border-t border-zinc-200 pt-3 font-mono text-xs text-zinc-600">
                  <div className="flex flex-wrap gap-2">
                    {item.documents.map((document) => (
                      <Link
                        key={document.id}
                        href={`/dashboard/onboarding/${item.id}/${document.id}`}
                        className="border-2 border-black bg-white px-3 py-2 font-mono text-[11px] font-black uppercase text-[#97192c] underline focus:ring-4 focus:ring-[#fc920d]/30"
                      >
                        {document.document_key.replaceAll("_", " ")} · {document.status}
                      </Link>
                    ))}
                  </div>
                </div>
              </article>
            ))
          )}
        </section>
      </div>
    </div>
  );
}
