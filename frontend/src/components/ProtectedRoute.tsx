import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

/**
 * Wraps authenticated routes. Redirects to /login if the session is
 * invalid, and renders nothing while the initial auth check is in flight.
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { authenticated } = useAuth();

  if (authenticated === null) {
    // Still checking — render nothing to avoid a flash of content.
    return null;
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;
