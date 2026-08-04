"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Mail, Plus, UserPlus } from "lucide-react";
import { useDyslexicStream } from "hooks/useDyslexicStream";
import {
  createContact,
  DyslexicApiError,
  formatDate,
  formatRelative,
  getCompany,
  getContactOutreach,
  OUTCOME_LABELS,
  recordOutcome,
  updateCompany,
  STAGE_LABELS,
  type CompanyDetail,
  type CompanyStage,
  type Contact,
  type Outcome,
  type Outreach,
} from "lib/dyslexic";
import { ErrorNote, StageBadge, StreamIndicator } from "./DyslexicChrome";
import GenerateEmailDialog from "./GenerateEmailDialog";
import ResearchPanel from "./ResearchPanel";

export default function CompanyDetailContent({ companyId }: { companyId: string }) {
  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddContact, setShowAddContact] = useState(false);
  const [drafting, setDrafting] = useState<{ contact: Contact; kind: "initial" | "follow_up" } | null>(null);
  const [outcomeFor, setOutcomeFor] = useState<Contact | null>(null);

  const load = useCallback(async () => {
    try {
      setCompany(await getCompany(companyId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this company.");
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  const { status } = useDyslexicStream(load);

  if (loading) {
    return <p className="p-8 text-center text-sm text-muted-foreground">Loading…</p>;
  }

  if (!company) {
    return <ErrorNote message={error ?? "Company not found."} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href="/dashboard/dyslexic/companies"
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-orange"
        >
          <ArrowLeft className="size-4" />
          All companies
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-heading font-bold">{company.name}</h1>
              <StageBadge stage={company.stage as CompanyStage} />
            </div>
            {company.website && (
              <a
                href={company.website}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-sm text-muted-foreground hover:text-orange"
              >
                {company.normalized_domain ?? company.website}
              </a>
            )}
          </div>

          <div className="flex items-center gap-3">
            <StreamIndicator status={status} />
            <select
              value={company.stage}
              onChange={async (event) => {
                await updateCompany(company.id, {
                  stage: event.target.value as CompanyStage,
                });
                load();
              }}
              className="rounded-base border-2 border-border bg-[#111] px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-main"
            >
              {Object.entries(STAGE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && <ErrorNote message={error} />}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-6">
          <ResearchPanel company={company} onRefresh={load} />

          <section className="rounded-base border-2 border-border bg-[#0d0d0d] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-sm font-bold uppercase tracking-widest text-muted-foreground">
                Contacts
              </h2>
              <button
                type="button"
                onClick={() => setShowAddContact(true)}
                className="flex items-center gap-1.5 rounded-base border-2 border-border px-2 py-1 text-xs font-medium hover:bg-white/5"
              >
                <UserPlus className="size-3" />
                Add contact
              </button>
            </div>

            {company.contacts.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No contacts yet. Add someone to reach out to.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {company.contacts.map((contact) => (
                  <ContactRow
                    key={contact.id}
                    contact={contact}
                    onDraft={(kind) => setDrafting({ contact, kind })}
                    onRecordOutcome={() => setOutcomeFor(contact)}
                  />
                ))}
              </ul>
            )}
          </section>
        </div>

        <section className="rounded-base border-2 border-border bg-[#0d0d0d] p-4">
          <h2 className="mb-3 font-heading text-sm font-bold uppercase tracking-widest text-muted-foreground">
            Timeline
          </h2>

          {company.timeline.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Nothing recorded yet.
            </p>
          ) : (
            <ol className="flex flex-col gap-3">
              {company.timeline.map((event) => (
                <li key={event.id} className="border-l-2 border-border pl-3">
                  <p className="text-sm leading-snug">{event.summary}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {formatRelative(event.created_at)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      {showAddContact && (
        <AddContactDialog
          companyId={company.id}
          onClose={() => setShowAddContact(false)}
          onCreated={() => {
            setShowAddContact(false);
            load();
          }}
        />
      )}

      {drafting && (
        <GenerateEmailDialog
          contact={drafting.contact}
          kind={drafting.kind}
          onClose={() => setDrafting(null)}
          onSent={() => {
            setDrafting(null);
            load();
          }}
        />
      )}

      {outcomeFor && (
        <OutcomeDialog
          contact={outcomeFor}
          onClose={() => setOutcomeFor(null)}
          onRecorded={() => {
            setOutcomeFor(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function ContactRow({
  contact,
  onDraft,
  onRecordOutcome,
}: {
  contact: Contact;
  onDraft: (kind: "initial" | "follow_up") => void;
  onRecordOutcome: () => void;
}) {
  const claimActive =
    contact.claimed_by &&
    contact.claim_expires_at &&
    new Date(contact.claim_expires_at) > new Date();

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-base border-2 border-border bg-[#111] px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">
          {contact.name}
          {contact.role && (
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {contact.role}
            </span>
          )}
        </p>

        <p className="truncate text-xs text-muted-foreground">
          {contact.email ?? "no email"}
          {contact.contacted_at && (
            <span className="ml-2 text-green-400">
              Contacted by {contact.contacted_by_name} · {formatDate(contact.contacted_at)}
            </span>
          )}
          {!contact.contacted_at && claimActive && (
            <span className="ml-2 text-orange">
              {contact.claimed_by_name} is drafting…
            </span>
          )}
        </p>
      </div>

      <div className="flex shrink-0 gap-2">
        {contact.contacted_at ? (
          <>
            <button
              type="button"
              onClick={onRecordOutcome}
              className="rounded-base border-2 border-border px-2 py-1 text-xs font-medium hover:bg-white/5"
            >
              Record outcome
            </button>
            <button
              type="button"
              onClick={() => onDraft("follow_up")}
              className="flex items-center gap-1.5 rounded-base border-2 border-border px-2 py-1 text-xs font-medium hover:bg-white/5"
            >
              <Mail className="size-3" />
              Follow up
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => onDraft("initial")}
            className="flex items-center gap-1.5 rounded-base border-2 border-border bg-main px-2 py-1 text-xs font-medium text-main-foreground hover:opacity-90"
          >
            <Mail className="size-3" />
            Write email
          </button>
        )}
      </div>
    </li>
  );
}

function AddContactDialog({
  companyId,
  onClose,
  onCreated,
}: {
  companyId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({ name: "", role: "", email: "", linkedin_url: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.name.trim() || saving) return;

    setSaving(true);
    setError(null);

    try {
      const created = await createContact(companyId, {
        name: form.name.trim(),
        role: form.role.trim() || undefined,
        email: form.email.trim() || undefined,
        linkedin_url: form.linkedin_url.trim() || undefined,
      });

      // Not a failure — the same person can legitimately be a contact at two
      // companies. Show it, then continue.
      if (created.duplicate_warning) {
        setWarning(created.duplicate_warning);
        setSaving(false);
        setTimeout(onCreated, 2500);
        return;
      }
      onCreated();
    } catch (err) {
      setError(
        err instanceof DyslexicApiError
          ? err.message
          : "Could not add the contact.",
      );
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />

      <form
        onSubmit={submit}
        className="relative z-10 w-full max-w-md rounded-base border-2 border-border bg-[#0d0d0d] p-5"
      >
        <h2 className="font-heading text-lg font-bold">Add a contact</h2>

        {(
          [
            { key: "name", label: "Name", placeholder: "Priya Sharma", autoFocus: true },
            { key: "role", label: "Role", placeholder: "Campus Marketing Lead" },
            { key: "email", label: "Email", placeholder: "priya@zomato.com" },
            { key: "linkedin_url", label: "LinkedIn", placeholder: "https://linkedin.com/in/…" },
          ] as const
        ).map((field) => (
          <label key={field.key} className="mt-3 block text-sm font-medium">
            {field.label}
            <input
              autoFocus={"autoFocus" in field ? field.autoFocus : false}
              value={form[field.key]}
              onChange={(event) =>
                setForm((current) => ({ ...current, [field.key]: event.target.value }))
              }
              placeholder={field.placeholder}
              className="mt-1 w-full rounded-base border-2 border-border bg-[#111] px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-main"
            />
          </label>
        ))}

        {warning && (
          <div className="mt-3 rounded-base border-2 border-orange/40 bg-orange/10 px-3 py-2 text-sm text-orange">
            {warning}
          </div>
        )}
        {error && (
          <div className="mt-3 rounded-base border-2 border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-base border-2 border-border px-3 py-2 text-sm font-medium hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !form.name.trim()}
            className="rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-medium text-main-foreground shadow-light disabled:opacity-50"
          >
            {saving ? "Adding…" : "Add contact"}
          </button>
        </div>
      </form>
    </div>
  );
}

function OutcomeDialog({
  contact,
  onClose,
  onRecorded,
}: {
  contact: Contact;
  onClose: () => void;
  onRecorded: () => void;
}) {
  const [outreach, setOutreach] = useState<Outreach[]>([]);
  const [outcome, setOutcome] = useState<Outcome>("no_reply");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getContactOutreach(contact.id).then(setOutreach).catch(() => {});
  }, [contact.id]);

  // Outcomes attach to the most recent send.
  const target = outreach[0];

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!target || saving) return;

    setSaving(true);
    setError(null);
    try {
      await recordOutcome(target.id, { outcome, note: note.trim() || undefined });
      onRecorded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record the outcome.");
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />

      <form
        onSubmit={submit}
        className="relative z-10 w-full max-w-md rounded-base border-2 border-border bg-[#0d0d0d] p-5"
      >
        <h2 className="font-heading text-lg font-bold">What happened?</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {contact.name}
          {target ? ` · emailed ${formatDate(target.sent_at)}` : ""}
        </p>

        <div className="mt-4 flex flex-col gap-2">
          {(Object.keys(OUTCOME_LABELS) as Outcome[]).map((value) => (
            <label
              key={value}
              className={`flex cursor-pointer items-center gap-3 rounded-base border-2 px-3 py-2 text-sm ${
                outcome === value
                  ? "border-main bg-main/10"
                  : "border-border hover:bg-white/5"
              }`}
            >
              <input
                type="radio"
                name="outcome"
                value={value}
                checked={outcome === value}
                onChange={() => setOutcome(value)}
                className="accent-main"
              />
              {OUTCOME_LABELS[value]}
            </label>
          ))}
        </div>

        <label className="mt-3 block text-sm font-medium">
          Note <span className="text-muted-foreground">(optional)</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            className="mt-1 w-full rounded-base border-2 border-border bg-[#111] px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-main"
          />
        </label>

        {error && (
          <div className="mt-3 rounded-base border-2 border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-base border-2 border-border px-3 py-2 text-sm font-medium hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !target}
            className="rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-medium text-main-foreground shadow-light disabled:opacity-50"
          >
            {saving ? "Saving…" : "Record"}
          </button>
        </div>
      </form>
    </div>
  );
}
