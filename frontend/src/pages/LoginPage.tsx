import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, setPassword } from "../api/auth";
import { ApiRequestError } from "../api/client";
import { useAuth } from "../hooks/useAuth";

function LoginPage() {
  const navigate = useNavigate();
  const { markAuthenticated } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPasswordVal] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isFirstTime, setIsFirstTime] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      markAuthenticated();
      navigate("/");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.error.code === "invalid_credentials") {
          setError("Invalid username or password.");
        } else {
          setError(err.error.message);
        }
      } else {
        setError("An unexpected error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSetPassword(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await setPassword(username, password);
      await login(username, password);
      markAuthenticated();
      navigate("/");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.error.code === "already_set") {
          setError("Password has already been set. Please log in instead.");
          setIsFirstTime(false);
        } else {
          setError(err.error.message);
        }
      } else {
        setError("An unexpected error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-center">
      <div className="card" style={{ maxWidth: 400, width: "100%" }}>
        <h1>BlackBook</h1>

        {!isFirstTime ? (
          <>
            <h2>Log In</h2>
            <form onSubmit={handleLogin}>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPasswordVal(e.target.value)}
                  required
                />
              </div>
              {error && <div className="error-message">{error}</div>}
              <button type="submit" disabled={loading}>
                {loading ? "Logging in..." : "Log In"}
              </button>
            </form>
            <p className="text-muted" style={{ marginTop: 16 }}>
              First time?{" "}
              <button
                className="link-button"
                onClick={() => {
                  setIsFirstTime(true);
                  setError("");
                }}
              >
                Set up your password
              </button>
            </p>
          </>
        ) : (
          <>
            <h2>First-Time Setup</h2>
            <form onSubmit={handleSetPassword}>
              <div className="form-group">
                <label htmlFor="setup-username">Username</label>
                <input
                  id="setup-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label htmlFor="setup-password">Password</label>
                <input
                  id="setup-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPasswordVal(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              <div className="form-group">
                <label htmlFor="confirm-password">Confirm Password</label>
                <input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              {error && <div className="error-message">{error}</div>}
              <button type="submit" disabled={loading}>
                {loading ? "Setting up..." : "Set Password & Log In"}
              </button>
            </form>
            <p className="text-muted" style={{ marginTop: 16 }}>
              Already set up?{" "}
              <button
                className="link-button"
                onClick={() => {
                  setIsFirstTime(false);
                  setError("");
                }}
              >
                Go to login
              </button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default LoginPage;
