/**
 * Typed fetch wrapper. Handles session cookie and error envelope parsing.
 */

const BASE_URL = "/api/v1";

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public error: ApiError,
  ) {
    super(error.message);
    this.name = "ApiRequestError";
  }
}

/**
 * Send a JSON API request. Returns the parsed response body.
 * Throws ApiRequestError on non-2xx responses.
 */
export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errorBody: ApiError;
    try {
      const body = await response.json();
      errorBody = body.error;
    } catch {
      errorBody = {
        code: "unknown",
        message: response.statusText || "Request failed",
      };
    }
    throw new ApiRequestError(response.status, errorBody);
  }

  // Handle empty responses (e.g., 204 No Content).
  const contentLength = response.headers.get("content-length");
  if (response.status === 204 || contentLength === "0") {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json() as Promise<T>;
  }

  // Non-JSON response — return text as unknown T.
  return (await response.text()) as unknown as T;
}

/**
 * Upload a file via multipart/form-data. Used for source file uploads (Phase 2+).
 */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: formData,
    // Do NOT set Content-Type — browser sets it with the boundary automatically.
  });

  if (!response.ok) {
    let errorBody: ApiError;
    try {
      const body = await response.json();
      errorBody = body.error;
    } catch {
      errorBody = {
        code: "unknown",
        message: response.statusText || "Upload failed",
      };
    }
    throw new ApiRequestError(response.status, errorBody);
  }

  return response.json() as Promise<T>;
}
