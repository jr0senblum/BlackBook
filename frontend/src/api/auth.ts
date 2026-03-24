/**
 * Authentication API functions.
 */

import { apiRequest } from "./client";

export async function login(username: string, password: string) {
  return apiRequest<{ ok: true }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout() {
  return apiRequest<{ ok: true }>("/auth/logout", {
    method: "POST",
  });
}

export async function setPassword(username: string, password: string) {
  return apiRequest<{ ok: true }>("/auth/password/set", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function changePassword(
  currentPassword: string,
  newPassword: string
) {
  return apiRequest<{ ok: true }>("/auth/password/change", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}
