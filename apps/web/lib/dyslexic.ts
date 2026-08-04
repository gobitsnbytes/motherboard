/**
 * Dyslexic API client.
 *
 * Every call goes to a relative /api/dyslexic/* URL so it passes through the
 * Next catch-all proxy, which signs the request with the current session. No
 * auth handling belongs here.
 */

export type CompanyStage =
  | "research"
  | "contacts_added"
  | "email_generated"
  | "email_sent"
  | "follow_up"
  | "replied"
  | "meeting"
  | "negotiation"
  | "sponsored"
  | "rejected";

export type ResearchStatus = "pending" | "running" | "complete" | "failed";

export type ResearchData = {
  summary?: string;
  industry?: string;
  size?: string;
  headquarters?: string;
  products?: string[];
  sponsorship_angle?: string;
  suggested_contact_roles?: string[];
  recent_news?: string[];
  confidence?: string;
  sources?: { title: string; url: string }[];
};

export type Company = {
  id: string;
  name: string;
  website: string | null;
  normalized_domain: string | null;
  stage: CompanyStage;
  research_status: ResearchStatus;
  research_json: ResearchData;
  research_error: string | null;
  research_generated_at: string | null;
  research_model: string | null;
  notes: string | null;
  added_by: string | null;
  fork_id: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  contact_count: number;
  added_by_name: string | null;
};

export type Contact = {
  id: string;
  company_id: string;
  name: string;
  role: string | null;
  email: string | null;
  linkedin_url: string | null;
  notes: string | null;
  status: string;
  contacted_by: string | null;
  contacted_at: string | null;
  claimed_by: string | null;
  claim_expires_at: string | null;
  added_by: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  contacted_by_name: string | null;
  claimed_by_name: string | null;
  company_name: string | null;
  duplicate_warning?: string | null;
};

export type TimelineEvent = {
  id: string;
  company_id: string;
  contact_id: string | null;
  actor_id: string | null;
  kind: string;
  summary: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  actor_name: string | null;
  actor_avatar: string | null;
  company_name: string | null;
};

export type CompanyDetail = Company & {
  contacts: Contact[];
  timeline: TimelineEvent[];
};

export type EmailDraft = {
  id: string;
  contact_id: string;
  company_id: string;
  kind: "initial" | "follow_up";
  subject: string;
  body: string;
  tone: string | null;
  model: string | null;
  generated_by: string | null;
  created_at: string;
};

export type Outreach = {
  id: string;
  contact_id: string;
  company_id: string;
  email_id: string | null;
  kind: "initial" | "follow_up";
  sent_by: string | null;
  sent_at: string;
  outcome: string | null;
  outcome_at: string | null;
  outcome_by: string | null;
  outcome_note: string | null;
  sent_by_name: string | null;
};

export type FollowUp = {
  id: string;
  outreach_id: string;
  contact_id: string;
  company_id: string;
  assigned_to: string | null;
  due_at: string;
  status: string;
  resolved_at: string | null;
  created_at: string;
  contact_name: string | null;
  company_name: string | null;
  assigned_to_name: string | null;
  is_overdue: boolean;
};

export type Stats = {
  companies: number;
  contacts: number;
  emails_sent: number;
  replies: number;
  follow_ups_due: number;
  my_follow_ups_due: number;
  sponsors_closed: number;
};

export type LeaderboardRow = {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  companies_added: number;
  contacts_added: number;
  emails_sent: number;
  follow_ups_sent: number;
  replies_received: number;
  meetings_scheduled: number;
  sponsors_closed: number;
  score: number;
};

export type Outcome =
  | "follow_up_sent"
  | "no_reply"
  | "replied"
  | "meeting_scheduled"
  | "sponsored"
  | "rejected";

/**
 * An API error that kept its structured detail.
 *
 * The backend returns objects for conflicts — who already contacted someone,
 * which company already exists — and the UI needs those fields to say anything
 * useful, so they must survive the throw.
 */
export class DyslexicApiError extends Error {
  status: number;
  detail: Record<string, unknown> | string;

  constructor(status: number, detail: Record<string, unknown> | string) {
    const message =
      typeof detail === "string"
        ? detail
        : (detail?.message as string) ?? "Something went wrong.";
    super(message);
    this.name = "DyslexicApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/dyslexic${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail: Record<string, unknown> | string = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? body;
    } catch {
      // Non-JSON error body — the status text is all we have.
    }
    throw new DyslexicApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// --- Dashboard ---

export const getStats = () => request<Stats>("/stats");

export const getActivity = (limit = 20) =>
  request<TimelineEvent[]>(`/activity?limit=${limit}`);

export const getLeaderboard = (period: "all" | "30d" = "all") =>
  request<LeaderboardRow[]>(`/leaderboard?period=${period}`);

// --- Companies ---

export function getCompanies(params: {
  stage?: string;
  q?: string;
  archived?: boolean;
} = {}) {
  const query = new URLSearchParams();
  if (params.stage) query.set("stage", params.stage);
  if (params.q) query.set("q", params.q);
  if (params.archived) query.set("archived", "true");
  const suffix = query.toString();
  return request<Company[]>(`/companies${suffix ? `?${suffix}` : ""}`);
}

export const getCompany = (id: string) =>
  request<CompanyDetail>(`/companies/${id}`);

export const createCompany = (body: {
  name: string;
  website?: string;
  notes?: string;
}) =>
  request<Company>("/companies", { method: "POST", body: JSON.stringify(body) });

export const updateCompany = (
  id: string,
  body: Partial<{
    name: string;
    website: string;
    notes: string;
    stage: CompanyStage;
    is_archived: boolean;
  }>,
) =>
  request<Company>(`/companies/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const rerunResearch = (id: string) =>
  request<{ status: string }>(`/companies/${id}/research`, { method: "POST" });

export const getTimeline = (id: string, limit = 50) =>
  request<TimelineEvent[]>(`/companies/${id}/timeline?limit=${limit}`);

// --- Contacts ---

export function getContacts(params: { status?: string; q?: string } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  const suffix = query.toString();
  return request<Contact[]>(`/contacts${suffix ? `?${suffix}` : ""}`);
}

export const createContact = (
  companyId: string,
  body: {
    name: string;
    role?: string;
    email?: string;
    linkedin_url?: string;
    notes?: string;
  },
) =>
  request<Contact>(`/companies/${companyId}/contacts`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateContact = (
  id: string,
  body: Partial<{ name: string; role: string; email: string; status: string }>,
) =>
  request<Contact>(`/contacts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const claimContact = (id: string) =>
  request<Contact>(`/contacts/${id}/claim`, { method: "POST" });

export const releaseClaim = (id: string) =>
  request<void>(`/contacts/${id}/claim`, { method: "DELETE" });

// --- Emails and outreach ---

export const generateEmail = (
  contactId: string,
  body: { kind: "initial" | "follow_up"; tone?: string; extra_context?: string },
) =>
  request<EmailDraft>(`/contacts/${contactId}/generate-email`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getEmails = (contactId: string) =>
  request<EmailDraft[]>(`/contacts/${contactId}/emails`);

export const markSent = (
  contactId: string,
  body: { kind: "initial" | "follow_up"; email_id?: string },
) =>
  request<Outreach>(`/contacts/${contactId}/sent`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getContactOutreach = (contactId: string) =>
  request<Outreach[]>(`/contacts/${contactId}/outreach`);

export const recordOutcome = (
  outreachId: string,
  body: { outcome: Outcome; note?: string },
) =>
  request<Outreach>(`/outreach/${outreachId}/outcome`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

// --- Follow-ups ---

export const getFollowUps = (scope: "mine" | "all" = "mine") =>
  request<FollowUp[]>(`/follow-ups?scope=${scope}&status=pending`);

export const resolveFollowUp = (id: string, note?: string) =>
  request<FollowUp>(`/follow-ups/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });

// --- Display helpers ---

export const STAGE_LABELS: Record<CompanyStage, string> = {
  research: "Research",
  contacts_added: "Contacts Added",
  email_generated: "Email Drafted",
  email_sent: "Email Sent",
  follow_up: "Follow-up",
  replied: "Replied",
  meeting: "Meeting",
  negotiation: "Negotiation",
  sponsored: "Sponsored",
  rejected: "Rejected",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  follow_up_sent: "Follow-up Sent",
  no_reply: "No Reply",
  replied: "Replied",
  meeting_scheduled: "Meeting Scheduled",
  sponsored: "Sponsored",
  rejected: "Rejected",
};

/** Neutral by default; only terminal and positive states get colour. */
export function stageVariant(stage: CompanyStage): string {
  if (stage === "sponsored") return "bg-green-500/15 text-green-400 border-green-500/40";
  if (stage === "rejected") return "bg-red-500/15 text-red-400 border-red-500/40";
  if (stage === "meeting" || stage === "negotiation")
    return "bg-orange/15 text-orange border-orange/40";
  if (stage === "replied") return "bg-blue-500/15 text-blue-400 border-blue-500/40";
  return "bg-white/5 text-white/70 border-white/20";
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatRelative(value: string): string {
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}
