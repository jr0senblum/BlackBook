import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { ApiRequestError } from "../api/client";
import { listCompanies } from "../api/companies";

interface AuthContextValue {
  /** null = still checking, true = authenticated, false = not authenticated */
  authenticated: boolean | null;
  /** Call after a successful login to flip state without a round-trip. */
  markAuthenticated: () => void;
  /** Call after logout to flip state. */
  markUnauthenticated: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  authenticated: null,
  markAuthenticated: () => {},
  markUnauthenticated: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        // Probe an authenticated endpoint with minimal payload.
        await listCompanies(1, 0);
        if (!cancelled) setAuthenticated(true);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiRequestError && err.status === 401) {
            setAuthenticated(false);
          } else {
            // Network error or server down — treat as unauthenticated
            // so user can attempt login.
            setAuthenticated(false);
          }
        }
      }
    }
    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  const markAuthenticated = useCallback(() => setAuthenticated(true), []);
  const markUnauthenticated = useCallback(() => setAuthenticated(false), []);

  return (
    <AuthContext.Provider
      value={{ authenticated, markAuthenticated, markUnauthenticated }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
