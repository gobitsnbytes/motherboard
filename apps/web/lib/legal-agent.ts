/**
 * Typed client helpers for the Legal Agent (email-native contract teammate).
 * All calls go through the Next.js /api proxy to apps/api.
 */

export interface AgentStats {
  inbox_processed_24h: number;
  contracts_in_review: number;
  out_for_signature: number;
  dotted_count: number;
  pending_nudges: number;
  last_poll_at: string | null;
}

export interface PipelineContractItem {
  id: string;
  title: string;
  counterparty: string;
  status: "in_review" | "out_for_signature" | "dotted" | string;
  raw_status: string;
  value: string;
  signatories_count: number;
  highest_risk: "none" | "low" | "medium" | "high" | string;
  created_at: string;
  days_in_stage: number;
  high_risks: number;
  medium_risks: number;
  low_risks: number;
}

export interface AskSourceChip {
  label: "OKF Rule" | "Executed Contract" | string;
  title: string;
}

export interface AskResponse {
  answer: string;
  sources: AskSourceChip[];
}

export async function fetchAgentStats(): Promise<AgentStats> {
  const res = await fetch("/api/contract-assistant/agent/stats");
  if (!res.ok) {
    throw new Error(`Agent stats unavailable (${res.status})`);
  }
  return res.json();
}

export async function fetchInboundContracts(): Promise<PipelineContractItem[]> {
  const res = await fetch("/api/contract-assistant/contracts?source=inbound_email");
  if (!res.ok) {
    throw new Error(`Inbound contracts unavailable (${res.status})`);
  }
  return res.json();
}

export async function askLegalAgent(question: string): Promise<AskResponse> {
  const res = await fetch("/api/contract-assistant/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    throw new Error(`Ask failed (${res.status})`);
  }
  return res.json();
}
