/**
 * Source API functions.
 */

import { apiRequest, apiUpload } from "./client";
import type {
  SourceDetail,
  SourceListResponse,
  SourceStatusResponse,
  SourceUploadResponse,
} from "../types";

export async function uploadSource(
  file: File,
  companyId?: string,
): Promise<SourceUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (companyId) {
    formData.append("company_id", companyId);
  }
  return apiUpload<SourceUploadResponse>("/sources/upload", formData);
}

export async function listSources(
  companyId: string,
  params?: { status?: string; limit?: number; offset?: number },
): Promise<SourceListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiRequest<SourceListResponse>(
    `/companies/${companyId}/sources${qs ? `?${qs}` : ""}`,
  );
}

export async function getSource(sourceId: string): Promise<SourceDetail> {
  return apiRequest<SourceDetail>(`/sources/${sourceId}`);
}

export async function getSourceStatus(
  sourceId: string,
): Promise<SourceStatusResponse> {
  return apiRequest<SourceStatusResponse>(`/sources/${sourceId}/status`);
}

export async function retrySource(
  sourceId: string,
): Promise<SourceUploadResponse> {
  return apiRequest<SourceUploadResponse>(`/sources/${sourceId}/retry`, {
    method: "POST",
  });
}
