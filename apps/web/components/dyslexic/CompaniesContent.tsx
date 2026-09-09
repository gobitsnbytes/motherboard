"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Search } from "lucide-react";
import { useDyslexicStream } from "hooks/useDyslexicStream";
import {
  createCompany,
  DyslexicApiError,
  formatDate,
  getCompanies,
  STAGE_LABELS,
  type Company,
  type CompanyStage,
} from "lib/dyslexic";
import {
  DyslexicTabs,
  ErrorNote,
  SectionHeader,
  StageBadge,
  StreamIndicator,
} from "./DyslexicChrome";

export default function CompaniesContent() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(async () => {
    try {
      setCompanies(await getCompanies({ stage: stage || undefined }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load companies.");
    } finally {
      setLoading(false);
    }
  }, [stage]);

  useEffect(() => {
    load();
  }, [load]);

  const { status } = useDyslexicStream(load);

  // Filtering client-side keeps typing responsive; the list is small enough
  // that a request per keystroke would be wasteful.
  const visible = companies.filter((company) => {
    const needle = search.trim().toLowerCase();
    if (!needle) return true;
    return (
      company.name.toLowerCase().includes(needle) ||
      (company.normalized_domain ?? "").includes(needle)
    );
  });

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        title="Companies"
        description="Sponsor prospects. Add a name and a website — research fills in the rest."
        action={
          <div className="flex items-center gap-3">
            <StreamIndicator status={status} />
            <button
              type="button"
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-medium text-main-foreground shadow-light transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none"
            >
              <Plus className="size-4" />
              Add Company
            </button>
          </div>
        }
      />
      <DyslexicTabs />

      {error && <ErrorNote message={error} />}

      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search companies…"
            className="w-full rounded-base border-2 border-border bg-background py-2 pl-10 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-main"
          />
        </div>

        <select
          value={stage}
          onChange={(event) => setStage(event.target.value)}
          className="rounded-base border-2 border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-main"
        >
          <option value="">All stages</option>
          {Object.entries(STAGE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-base border-2 border-border">
        <table className="w-full min-w-[720px]">
          <thead>
            <tr className="border-b-2 border-border bg-muted text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-heading">Company</th>
              <th className="px-4 py-3 font-heading">Stage</th>
              <th className="px-4 py-3 font-heading">Contacts</th>
              <th className="px-4 py-3 font-heading">Research</th>
              <th className="px-4 py-3 font-heading">Added by</th>
              <th className="px-4 py-3 font-heading">Added</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-sm text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-sm text-muted-foreground">
                  {companies.length === 0
                    ? "No companies yet. Add the first one."
                    : "Nothing matches that search."}
                </td>
              </tr>
            ) : (
              visible.map((company) => (
                <tr
                  key={company.id}
                  onClick={() => router.push(`/dashboard/dyslexic/companies/${company.id}`)}
                  className="cursor-pointer border-b border-border/50 transition-colors last:border-0 hover:bg-white/5"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium">{company.name}</span>
                    {company.normalized_domain && (
                      <span className="block text-xs text-muted-foreground">
                        {company.normalized_domain}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StageBadge stage={company.stage as CompanyStage} />
                  </td>
                  <td className="px-4 py-3 text-sm">{company.contact_count}</td>
                  <td className="px-4 py-3">
                    <ResearchDot status={company.research_status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {company.added_by_name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatDate(company.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <AddCompanyDialog
          onClose={() => setShowAdd(false)}
          onCreated={(company) => {
            setShowAdd(false);
            router.push(`/dashboard/dyslexic/companies/${company.id}`);
          }}
        />
      )}
    </div>
  );
}

function ResearchDot({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    pending: { label: "Queued", className: "text-muted-foreground" },
    running: { label: "Researching…", className: "text-orange animate-pulse" },
    complete: { label: "Ready", className: "text-green-400" },
    failed: { label: "Failed", className: "text-red-400" },
  };
  const entry = config[status] ?? { label: "Queued", className: "text-muted-foreground" };
  return <span className={`text-xs ${entry.className}`}>{entry.label}</span>;
}

function AddCompanyDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (company: Company) => void;
}) {
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingId, setExistingId] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || saving) return;

    setSaving(true);
    setError(null);
    setExistingId(null);

    try {
      onCreated(
        await createCompany({
          name: name.trim(),
          website: website.trim() || undefined,
        }),
      );
    } catch (err) {
      if (err instanceof DyslexicApiError && err.status === 409) {
        // Someone already added it — offer the record rather than a dead end.
        const detail = err.detail as Record<string, string>;
        setExistingId(detail.existing_company_id ?? null);
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Could not add the company.");
      }
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />

      <form
        onSubmit={submit}
        className="relative z-10 w-full max-w-md rounded-base border-2 border-border bg-secondary-background p-5"
      >
        <h2 className="font-heading text-lg font-bold">Add a company</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Just the name and website. AI research runs automatically.
        </p>

        <label className="mt-4 block text-sm font-medium">
          Company name
          <input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Zomato"
            className="mt-1 w-full rounded-base border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-main"
          />
        </label>

        <label className="mt-3 block text-sm font-medium">
          Website <span className="text-muted-foreground">(optional)</span>
          <input
            value={website}
            onChange={(event) => setWebsite(event.target.value)}
            placeholder="https://zomato.com"
            className="mt-1 w-full rounded-base border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-main"
          />
        </label>

        {error && (
          <div className="mt-3 rounded-base border-2 border-orange/40 bg-orange/10 px-3 py-2 text-sm text-orange">
            {error}
            {existingId && (
              <Link
                href={`/dashboard/dyslexic/companies/${existingId}`}
                className="mt-1 block underline"
              >
                Open the existing record
              </Link>
            )}
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
            disabled={saving || !name.trim()}
            className="rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-medium text-main-foreground shadow-light transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50"
          >
            {saving ? "Adding…" : "Add company"}
          </button>
        </div>
      </form>
    </div>
  );
}
