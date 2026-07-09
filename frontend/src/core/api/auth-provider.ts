import { type User } from "@/core/auth/types";

import { clientFetch } from "./client";

export type { User };

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

/**
 * Fetch current user from FastAPI
 * Used when initialUser might be stale (e.g., after tab was inactive)
 */
export async function fetchCurrentUser(): Promise<User | null> {
  try {
    const res = await clientFetch("/api/v1/auth/me", {
      redirectOn401: false,
    });

    if (res.ok) {
      return await res.json();
    } else if (res.status === 401) {
      return null;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Logout - call FastAPI logout endpoint
 * Returns true if logout was successful
 */
export async function performLogout(): Promise<boolean> {
  try {
    await clientFetch("/api/v1/auth/logout", {
      method: "POST",
      redirectOn401: false,
    });
    return true;
  } catch {
    return false;
  }
}
