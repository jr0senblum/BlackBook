/**
 * Pending review API functions.
 */

import { apiRequest } from "./client";
import type {
  AcceptResponse,
  DismissResponse,
  PendingFactListResponse,
} from "../types";

export async function listPending(
  companyId: string,
  params?: {
    status?: string;
    category?: string;
    limit?: number;
    offset?: number;
  },
): Promise<PendingFactListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.category) query.set("category", params.category);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiRequest<PendingFactListResponse>(
    `/companies/${companyId}/pending${qs ? `?${qs}` : ""}`,
  );
}

export async function acceptFact(
  companyId: string,
  factId: string,
): Promise<AcceptResponse> {
  return apiRequest<AcceptResponse>(
    `/companies/${companyId}/pending/${factId}/accept`,
    { method: "POST" },
  );
}

export async function dismissFact(
  companyId: string,
  factId: string,
): Promise<DismissResponse> {
  return apiRequest<DismissResponse>(
    `/companies/${companyId}/pending/${factId}/dismiss`,
    { method: "POST" },
  );
}
