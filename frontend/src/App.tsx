import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import CompanyListPage from "./pages/CompanyListPage";
import CompanyProfilePage from "./pages/CompanyProfilePage";
import SettingsPage from "./pages/SettingsPage";
import NavBar from "./components/NavBar";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Authenticated routes — NavBar is rendered for all */}
        <Route
          path="/"
          element={
            <Layout>
              <CompanyListPage />
            </Layout>
          }
        />
        <Route
          path="/companies/:id"
          element={
            <Layout>
              <CompanyProfilePage />
            </Layout>
          }
        />
        <Route
          path="/settings"
          element={
            <Layout>
              <SettingsPage />
            </Layout>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

/**
 * Layout wrapper that adds the NavBar above the page content.
 * Auth checking is done inside each page (redirects to /login on 401).
 */
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <NavBar />
      {children}
    </>
  );
}

export default App;
