const API = "/api/plugins/mailroom";

export type AiPreferences = {
  tone: string;
  signature: string;
  auto_triage: boolean;
};

export type Session = {
  authenticated: boolean;
  email: string | null;
  accounts: string[];
  preferences: AiPreferences;
};

export type Folder = {
  name: string;
  display_name: string;
  role: string | null;
  total: number;
  unread: number;
};

export type Summary = {
  uid: string;
  folder: string;
  sender: string;
  to: string;
  subject: string;
  date: string | null;
  unread: boolean;
  flagged: boolean;
  has_attachments: boolean;
  snippet: string;
};

export type MessageList = {
  folder: string;
  total: number;
  offset: number;
  messages: Summary[];
};

export type Attachment = {
  index: number;
  filename: string;
  content_type: string;
  size: number;
};

export type LinkTarget = { href: string; text: string };

export type ThreadNeighbour = {
  uid: string;
  subject: string;
  sender: string;
  date: string | null;
};

export type MailMessage = {
  uid: string;
  folder: string;
  message_id: string | null;
  sender: string;
  to: string;
  cc: string;
  subject: string;
  date: string | null;
  text: string;
  html: string | null;
  remote_images_blocked: number;
  links: LinkTarget[];
  attachments: Attachment[];
  thread: ThreadNeighbour[];
};

export type Draft = {
  to: string;
  cc: string;
  bcc: string;
  subject: string;
  body: string;
  in_reply_to?: string | null;
  references?: string | null;
};

export type AssistantAction = "summarize" | "reply" | "rewrite" | "triage";

export type AssistantResult = {
  action: AssistantAction;
  summary: string | null;
  body: string | null;
  suggestion: string | null;
  reason: string | null;
};

/** Thrown when the mail password stopped working; the caller returns to sign in. */
export class MailAuthError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail || "Mailroom could not complete that request";
    throw response.status === 401 ? new MailAuthError(detail) : new Error(detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function query(params: Record<string, string | number | boolean | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

export function attachmentUrl(
  message: MailMessage,
  attachment: Attachment,
  account: string,
) {
  return `${API}/messages/${message.uid}/attachments/${attachment.index}${query({
    folder: message.folder,
    account,
  })}`;
}

export function rawUrl(message: MailMessage, account: string) {
  return `${API}/messages/${message.uid}/raw${query({ folder: message.folder, account })}`;
}

export function send(draft: Draft, account: string, idempotencyKey: string) {
  return api<{ message_id: string; duplicate: boolean }>(`/messages${query({ account })}`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(draft),
  });
}

export function runAssistant(
  body: {
    action: AssistantAction;
    folder?: string;
    uid?: string | null;
    instruction?: string;
    draft?: string;
  },
  account: string,
) {
  return api<AssistantResult>(`/assistant${query({ account })}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function friendlyDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const sameDay = new Date().toDateString() === date.toDateString();
  return new Intl.DateTimeFormat(
    undefined,
    sameDay ? { hour: "numeric", minute: "2-digit" } : { month: "short", day: "numeric" },
  ).format(date);
}

export function fullDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function readableSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
