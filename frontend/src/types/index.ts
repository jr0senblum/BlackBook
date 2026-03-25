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
}
