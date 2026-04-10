/**
 * Shared TypeScript type definitions.
 */

// ── API ─────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface OkResponse {
  ok: true;
}

// ── Company ─────────────────────────────────────────────────────

export interface CompanyListItem {
  id: string;
  name: string;
  updated_at: string;
  pending_count: number;
}

export interface CompanyListResponse {
  total: number;
  limit: number;
  offset: number;
  items: CompanyListItem[];
}

export interface CompanyCreatedResponse {
  company_id: string;
  name: string;
}

export interface CompanyDetail {
  id: string;
  name: string;
  mission: string | null;
  vision: string | null;
  llm_context_mode: string;
  created_at: string;
  updated_at: string;
  pending_count: number;
}

export interface CompanyCreateInput {
  name: string;
  mission?: string;
  vision?: string;
}

export interface CompanyUpdateInput {
  name?: string;
  mission?: string;
  vision?: string;
  llm_context_mode?: string;
}

// ── Sources ─────────────────────────────────────────────────────

export interface SourceUploadResponse {
  source_id: string;
  status: string;
}

export interface SourceListItem {
  source_id: string;
  type: string;
  subject_or_filename: string | null;
  received_at: string;
  status: string;
  error: string | null;
}

export interface SourceListResponse {
  total: number;
  limit: number;
  offset: number;
  items: SourceListItem[];
}

export interface SourceDetail {
  source_id: string;
  company_id: string;
  type: string;
  subject_or_filename: string | null;
  raw_content: string;
  received_at: string;
  who: string | null;
  interaction_date: string | null;
  src: string | null;
  status: string;
  error: string | null;
}

export interface SourceStatusResponse {
  source_id: string;
  status: string;
}

// ── Pending Review ──────────────────────────────────────────────

export interface PendingFactItem {
  fact_id: string;
  category: string;
  inferred_value: string;
  status: string;
  source_id: string;
  source_excerpt: string;
  candidates: unknown[];
}

export interface PendingFactListResponse {
  total: number;
  limit: number;
  offset: number;
  items: PendingFactItem[];
}

export interface AcceptResponse {
  fact_id: string;
  status: string;
  entity_id: string | null;
}

export interface DismissResponse {
  fact_id: string;
  status: string;
}
