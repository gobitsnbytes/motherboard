"use client";

import { useState } from "react";
import { AlertTriangle, ExternalLink, RefreshCw, Sparkles } from "lucide-react";
import { rerunResearch, type Company, type ResearchData } from "lib/dyslexic";

/**
 * AI research for a company.
 *
 * Research is advisory: a failure shows what went wrong and offers a retry, and
 * the rest of the page keeps working. Sources are listed so a volunteer can
 * check anything before repeating it to a sponsor.
 */
export default function ResearchPanel({
  company,
  onRefresh,
}: {
  company: Company;
  onRefresh: () => void;
}) {
  const [retrying, setRetrying] = useState(false);

  async function retry() {
    setRetrying(true);
    try {
      await rerunResearch(company.id);
      onRefresh();
    } finally {
      setRetrying(false);
    }
  }

  const research: ResearchData = company.research_json ?? {};

  if (company.research_status === "pending" || company.research_status === "running") {
    return (
      <section className="rounded-base border-2 border-border bg-[#0d0d0d] p-4">
        <Header />
        <div className="flex items-center gap-3 py-6 text-sm text-muted-foreground">
          <Sparkles className="size-4 animate-pulse text-orange" />
          Researching {company.name}… this usually takes a few seconds.
        </div>
      </section>
    );
  }

  if (company.research_status === "failed") {
    return (
      <section className="rounded-base border-2 border-border bg-[#0d0d0d] p-4">
        <Header />
        <div className="flex items-start gap-3 rounded-base border-2 border-orange/40 bg-orange/10 p-3">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-orange" />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-orange">
              {company.research_error ?? "Research could not be completed."}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              You can still add contacts and log outreach — research is optional.
            </p>
          </div>
          <button
            type="button"
            onClick={retry}
            disabled={retrying}
            className="flex shrink-0 items-center gap-1.5 rounded-base border-2 border-border px-2 py-1 text-xs font-medium hover:bg-white/5 disabled:opacity-50"
          >
            <RefreshCw className={`size-3 ${retrying ? "animate-spin" : ""}`} />
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-base border-2 border-border bg-[#0d0d0d] p-4">
      <Header onRetry={retry} retrying={retrying} />

      {research.summary && <p className="mb-4 text-sm leading-relaxed">{research.summary}</p>}

      <dl className="grid gap-3 sm:grid-cols-2">
        <Field label="Industry" value={research.industry} />
        <Field label="Size" value={research.size} />
        <Field label="Headquarters" value={research.headquarters} />
        <Field label="Confidence" value={research.confidence} />
      </dl>

      {research.sponsorship_angle && (
        <div className="mt-4 rounded-base border-2 border-border bg-[#111] p-3">
          <p className="mb-1 font-heading text-xs uppercase tracking-wider text-muted-foreground">
            Why they might sponsor
          </p>
          <p className="text-sm">{research.sponsorship_angle}</p>
        </div>
      )}

      {!!research.suggested_contact_roles?.length && (
        <ListBlock label="Worth contacting" items={research.suggested_contact_roles} />
      )}
      {!!research.products?.length && (
        <ListBlock label="Products" items={research.products} />
      )}
      {!!research.recent_news?.length && (
        <ListBlock label="Recent news" items={research.recent_news} />
      )}

      {!!research.sources?.length && (
        <div className="mt-4 border-t border-border/50 pt-3">
          <p className="mb-2 font-heading text-xs uppercase tracking-wider text-muted-foreground">
            Sources
          </p>
          <ul className="flex flex-col gap-1">
            {research.sources.map((source) => (
              <li key={source.url}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-orange"
                >
                  <ExternalLink className="size-3 shrink-0" />
                  <span className="truncate">{source.title}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Header({ onRetry, retrying }: { onRetry?: () => void; retrying?: boolean }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="font-heading text-sm font-bold uppercase tracking-widest text-muted-foreground">
        Research
      </h2>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-orange disabled:opacity-50"
        >
          <RefreshCw className={`size-3 ${retrying ? "animate-spin" : ""}`} />
          Refresh
        </button>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <dt className="font-heading text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}

function ListBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="mt-4">
      <p className="mb-1 font-heading text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-base border border-white/20 bg-white/5 px-2 py-0.5 text-xs"
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
