import { BrowserRouter, Routes, Route } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import CompanyListPage from "./pages/CompanyListPage";
import CompanyProfilePage from "./pages/CompanyProfilePage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<CompanyListPage />} />
        <Route path="/companies/:id" element={<CompanyProfilePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
