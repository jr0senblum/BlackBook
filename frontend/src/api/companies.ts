/**
 * Company API functions.
 */

import { apiRequest } from "./client";
import type {
  CompanyCreatedResponse,
  CompanyCreateInput,
  CompanyDetail,
  CompanyListResponse,
  CompanyUpdateInput,
} from "../types";

export async function listCompanies(
  limit = 100,
  offset = 0,
): Promise<CompanyListResponse> {
  return apiRequest<CompanyListResponse>(
    `/companies?limit=${limit}&offset=${offset}`,
  );
}

export async function createCompany(
  input: CompanyCreateInput,
): Promise<CompanyCreatedResponse> {
  return apiRequest<CompanyCreatedResponse>("/companies", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getCompany(id: string): Promise<CompanyDetail> {
  return apiRequest<CompanyDetail>(`/companies/${id}`);
}

export async function updateCompany(
  id: string,
  input: CompanyUpdateInput,
): Promise<CompanyDetail> {
  return apiRequest<CompanyDetail>(`/companies/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteCompany(id: string): Promise<void> {
  return apiRequest<void>(`/companies/${id}`, {
    method: "DELETE",
  });
}
