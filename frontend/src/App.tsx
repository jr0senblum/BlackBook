import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import CompanyListPage from "./pages/CompanyListPage";
import CompanyProfilePage from "./pages/CompanyProfilePage";
import SettingsPage from "./pages/SettingsPage";
import NavBar from "./components/NavBar";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./hooks/useAuth";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />

          {/* Authenticated routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout>
                  <CompanyListPage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/companies/:id"
            element={
              <ProtectedRoute>
                <Layout>
                  <CompanyProfilePage />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Layout>
                  <SettingsPage />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

/** Layout wrapper that adds the NavBar above the page content. */
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <NavBar />
      {children}
    </>
  );
}

export default App;
