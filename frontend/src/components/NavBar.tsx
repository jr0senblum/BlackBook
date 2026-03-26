import { useNavigate } from "react-router-dom";
import { logout } from "../api/auth";
import { useAuth } from "../hooks/useAuth";

function NavBar() {
  const navigate = useNavigate();
  const { markUnauthenticated } = useAuth();

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Even if the server rejects, clear client state.
    }
    markUnauthenticated();
    navigate("/login");
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand" onClick={() => navigate("/")}>
        BlackBook
      </div>
      <div className="navbar-links">
        <button className="nav-link" onClick={() => navigate("/")}>
          Companies
        </button>
        <button className="nav-link" onClick={() => navigate("/settings")}>
          Settings
        </button>
        <button className="nav-link" onClick={() => void handleLogout()}>
          Logout
        </button>
      </div>
    </nav>
  );
}

export default NavBar;
